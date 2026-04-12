"""Lazy Langfuse SDK singleton. Returns None when credentials are absent."""

import threading

from langfuse import Langfuse
from langfuse.span_filter import is_default_export_span
from opentelemetry.sdk.trace import ReadableSpan

from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_client: Langfuse | None = None
_initialized = False
_lock = threading.Lock()


def _should_export_span(span: ReadableSpan) -> bool:
    """Langfuse export filter that also accepts pathfinder app spans.

    Langfuse's default filter (``is_default_export_span``) only keeps spans
    from known LLM instrumentors or spans with ``gen_ai.*`` attributes. Our
    turn-level span (``chat.turn``) is created by the ``pathfinder.pipeline``
    tracer and carries only ``langfuse.*`` / ``app.*`` attributes, so the
    default filter drops it and its root-trace metadata never reaches
    Langfuse. Accept any span that explicitly sets ``langfuse.*`` attributes.
    """
    if is_default_export_span(span):
        return True
    return any(
        key.startswith("langfuse.")
        for key in (span.attributes or {})
    )


def get_langfuse() -> Langfuse | None:
    """Return the Langfuse SDK client, or None when not configured.

    Thread-safe lazy initialization. The client is created once and reused.
    """
    global _client, _initialized  # noqa: PLW0603
    if _initialized:
        return _client

    with _lock:
        if _initialized:
            return _client

        settings = get_settings()
        if not settings.langfuse_secret_key:
            logger.info("Langfuse SDK disabled (no LANGFUSE_SECRET_KEY)")
            _initialized = True
            return None

        _client = Langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
            should_export_span=_should_export_span,
        )
        _initialized = True
        logger.info("Langfuse SDK initialized", host=settings.langfuse_host)
        return _client


def shutdown_langfuse() -> None:
    """Flush and shutdown the Langfuse client. Called during app shutdown."""
    global _client, _initialized  # noqa: PLW0603
    if _client is not None:
        _client.shutdown()
        _client = None
    _initialized = False
