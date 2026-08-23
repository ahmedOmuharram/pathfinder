"""Record user feedback (thumbs up/down) as Langfuse scores."""

import langfuse.api
from assistant_core.platform.logging import get_logger

from pathfinder.platform.langfuse.client import get_langfuse

logger = get_logger(__name__)

# Langfuse SDK can raise langfuse.api.Error (API/network), ValueError
# (invalid args), or OSError (DNS/socket).
_LANGFUSE_ERRORS = (langfuse.api.Error, ValueError, OSError)


def record_feedback(
    *,
    trace_id: str,
    stream_id: str,
    value: int,
    comment: str | None = None,
) -> None:
    """Record a user feedback score on a trace. No-op when Langfuse disabled."""
    client = get_langfuse()
    if client is None:
        logger.debug("Feedback discarded (Langfuse disabled)")
        return

    try:
        client.create_score(
            trace_id=trace_id,
            name="user_feedback",
            value=value,
            data_type="BOOLEAN",
            comment=comment,
        )
        logger.info(
            "User feedback recorded",
            trace_id=trace_id,
            stream_id=stream_id,
            value=value,
        )
    except _LANGFUSE_ERRORS:
        logger.warning("Failed to record feedback", trace_id=trace_id, exc_info=True)
