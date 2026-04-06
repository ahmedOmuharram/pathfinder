"""Observability setup for PathFinder: OTEL + Langfuse + pydantic-ai instrumentation."""

import base64
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import set_tracer_provider
from pydantic_ai import Agent, InstrumentationSettings


def setup_observability() -> None:
    """Configure OTEL + Langfuse if credentials are available.

    No-ops when LANGFUSE_SECRET_KEY is not set.
    """
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not secret_key:
        return

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")

    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    exporter = OTLPSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {auth}"},
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    set_tracer_provider(provider)

    Agent.instrument_all(InstrumentationSettings(version=3))


def get_tracer() -> trace.Tracer:
    """Return a tracer for custom spans (e.g. state machine transitions)."""
    return trace.get_tracer("pathfinder.pipeline")
