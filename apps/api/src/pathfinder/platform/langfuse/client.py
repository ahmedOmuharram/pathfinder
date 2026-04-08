"""Lazy Langfuse SDK singleton. Returns None when credentials are absent."""

import threading

from langfuse import Langfuse

from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

_client: Langfuse | None = None
_initialized = False
_lock = threading.Lock()


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
