"""Core stream-part registry. Products register their own parts onto it."""

from assistant_core.conversation.stream_parts.core_parts import (
    register_core_stream_parts,
)
from assistant_core.conversation.stream_parts.registry import (
    StreamPartRegistry,
)

STREAM_PARTS = StreamPartRegistry()
register_core_stream_parts(STREAM_PARTS)
