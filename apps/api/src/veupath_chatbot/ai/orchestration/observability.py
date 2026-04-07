"""Observability setup: dual OTEL export (SigNoz + Langfuse) + library instrumentation.

Each instrumentation concern is a standalone function that no-ops gracefully
when its prerequisite is missing.  ``setup_observability`` composes them.
"""

import base64
import logging
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as importlib_version
from uuid import uuid4

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter as GrpcLogExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GrpcSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HttpSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic_ai import Agent, InstrumentationSettings

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import (
    request_id_ctx,
    site_id_ctx,
    user_id_ctx,
)
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

class _OtelState:
    """Module-level mutable state for OTEL providers (avoids ``global``)."""

    provider: TracerProvider | None = None
    meter_provider: MeterProvider | None = None


_otel = _OtelState()


def _get_version() -> str:
    """Read the package version from installed metadata."""
    try:
        return importlib_version("pathfinder-api")
    except PackageNotFoundError:
        return "0.0.0-dev"


def _build_resource() -> Resource:
    """Build the OTEL Resource with enriched semantic convention attributes."""
    settings = get_settings()
    return Resource.create(
        {
            "service.name": "pathfinder-api",
            "service.version": _get_version(),
            "deployment.environment.name": settings.api_env,
            "service.instance.id": str(uuid4()),
        }
    )


def _configure_exporters() -> TracerProvider | None:
    """Create a TracerProvider with exporters for configured backends.

    Returns None when no backend is configured (complete no-op).
    """
    settings = get_settings()
    processors: list[BatchSpanProcessor] = []

    if settings.signoz_otel_endpoint:
        signoz_exporter = GrpcSpanExporter(
            endpoint=settings.signoz_otel_endpoint,
            insecure=True,
        )
        processors.append(BatchSpanProcessor(signoz_exporter))
        logger.info("OTEL exporter: SigNoz", endpoint=settings.signoz_otel_endpoint)

    if settings.langfuse_secret_key:
        auth = base64.b64encode(
            f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
        ).decode()
        langfuse_exporter = HttpSpanExporter(
            endpoint=f"{settings.langfuse_host}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth}"},
        )
        processors.append(BatchSpanProcessor(langfuse_exporter))
        logger.info("OTEL exporter: Langfuse", host=settings.langfuse_host)

    if not processors:
        return None

    _otel.provider = TracerProvider(resource=_build_resource())
    for proc in processors:
        _otel.provider.add_span_processor(proc)
    return _otel.provider


def _configure_metrics_export(resource: Resource) -> None:
    """Create a MeterProvider with a SigNoz gRPC exporter.

    No-ops when SigNoz is not configured (Langfuse does not support OTEL
    metrics ingestion).
    """
    settings = get_settings()
    if not settings.signoz_otel_endpoint:
        return

    exporter = OTLPMetricExporter(
        endpoint=settings.signoz_otel_endpoint,
        insecure=True,
    )
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=15_000)
    _otel.meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(_otel.meter_provider)
    logger.info("OTEL metrics: SigNoz", endpoint=settings.signoz_otel_endpoint)


def _configure_log_export() -> None:
    """Attach an OTLP log handler to the root logger for SigNoz.

    Enables one-click trace-to-log correlation in SigNoz by shipping
    structured logs (with trace_id/span_id) via the OTel Collector.
    No-ops when SigNoz is not configured.  The existing stdout handler
    is unaffected (dual output).
    """
    settings = get_settings()
    if not settings.signoz_otel_endpoint:
        return

    log_exporter = GrpcLogExporter(
        endpoint=settings.signoz_otel_endpoint,
        insecure=True,
    )
    log_provider = LoggerProvider(resource=_build_resource())
    log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(log_provider)

    handler = LoggingHandler(level=logging.DEBUG, logger_provider=log_provider)
    logging.getLogger().addHandler(handler)
    logger.info("OTLP log export: SigNoz", endpoint=settings.signoz_otel_endpoint)


def _instrument_fastapi(app: FastAPI) -> None:
    """Instrument FastAPI with per-request spans."""

    def server_request_hook(span: trace.Span, scope: dict[str, object]) -> None:
        if not span.is_recording():
            return
        uid = user_id_ctx.get()
        if uid is not None:
            span.set_attribute("app.user_id", str(uid))
        sid = site_id_ctx.get()
        if sid is not None:
            span.set_attribute("app.site_id", sid)
        rid = request_id_ctx.get()
        if rid is not None:
            span.set_attribute("app.request_id", rid)

    FastAPIInstrumentor.instrument_app(
        app,
        server_request_hook=server_request_hook,
        excluded_urls="health",
    )
    logger.info("Instrumented: FastAPI")


def _instrument_database(db_engine: object) -> None:
    """Instrument SQLAlchemy with per-query spans."""
    sync_engine = getattr(db_engine, "sync_engine", db_engine)
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)
    logger.info("Instrumented: SQLAlchemy")


def _instrument_http_clients() -> None:
    """Instrument httpx with per-outgoing-request spans."""
    HTTPXClientInstrumentor().instrument()
    logger.info("Instrumented: httpx")


def _instrument_redis() -> None:
    """Instrument Redis with per-command spans."""
    RedisInstrumentor().instrument()
    logger.info("Instrumented: Redis")


def _instrument_agents() -> None:
    """Instrument pydantic-ai agents with per-run/model/tool spans."""
    Agent.instrument_all(InstrumentationSettings(include_content=True))
    logger.info("Instrumented: pydantic-ai agents")


def setup_observability(
    *,
    app: FastAPI | None = None,
    db_engine: object | None = None,
) -> None:
    """Configure OTEL exporters and library instrumentation.

    No-ops entirely when neither SigNoz nor Langfuse is configured.
    """
    provider = _configure_exporters()
    if provider is None:
        logger.info(
            "Observability disabled (no SIGNOZ_OTEL_ENDPOINT or LANGFUSE_SECRET_KEY)"
        )
        return

    trace.set_tracer_provider(provider)
    _configure_metrics_export(provider.resource)
    _configure_log_export()

    if app is not None:
        _instrument_fastapi(app)
    if db_engine is not None:
        _instrument_database(db_engine)
    _instrument_http_clients()
    _instrument_redis()
    _instrument_agents()


def shutdown_observability() -> None:
    """Flush and shutdown OTEL providers. Called during app shutdown."""
    if _otel.meter_provider is not None:
        _otel.meter_provider.shutdown()
        _otel.meter_provider = None
    if _otel.provider is not None:
        _otel.provider.shutdown()
        _otel.provider = None
    logger.info("OTEL providers shut down")


def get_tracer() -> trace.Tracer:
    """Return a tracer for custom spans (pipeline phases, classification)."""
    return trace.get_tracer("pathfinder.pipeline")


def get_meter() -> metrics.Meter:
    """Return a meter for ad-hoc custom metrics."""
    return metrics.get_meter("pathfinder.pipeline")
