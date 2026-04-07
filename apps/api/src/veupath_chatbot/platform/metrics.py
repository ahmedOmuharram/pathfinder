"""Application-level OTEL metric instruments.

Instruments are created eagerly on the global OTEL metrics API.  Before a
real ``MeterProvider`` is configured (via :func:`setup_observability`), they
record to a no-op sink.  Once the provider is set, the proxy instruments
forward to the real exporter automatically.

Defined in ``platform/`` so that every layer (integrations, services, AI)
can import without violating architecture boundaries.
"""

from opentelemetry import metrics

_pipeline_meter = metrics.get_meter("pathfinder.pipeline")
_wdk_meter = metrics.get_meter("pathfinder.wdk")

# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

pipeline_runs = _pipeline_meter.create_counter(
    "pathfinder.pipeline.runs",
    description="Total pipeline runs by intent and outcome",
    unit="{run}",
)

phase_duration_s = _pipeline_meter.create_histogram(
    "pathfinder.pipeline.phase_duration",
    description="Duration of each pipeline phase",
    unit="s",
)

token_usage = _pipeline_meter.create_counter(
    "pathfinder.tokens.usage",
    description="Token consumption by model and type",
    unit="{token}",
)

pipeline_errors = _pipeline_meter.create_counter(
    "pathfinder.pipeline.errors",
    description="Pipeline errors by type and phase",
    unit="{error}",
)

# ---------------------------------------------------------------------------
# WDK metrics
# ---------------------------------------------------------------------------

wdk_request_duration_s = _wdk_meter.create_histogram(
    "pathfinder.wdk.request_duration",
    description="WDK HTTP request duration including retries",
    unit="s",
)
