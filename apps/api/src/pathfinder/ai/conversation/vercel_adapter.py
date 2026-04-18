"""Per-phase AI SDK v6 chunk emitter for the LangGraph chat pipeline.

Wraps :class:`pydantic_ai.ui.vercel_ai._event_stream.VercelAIEventStream`
so each graph node can forward pydantic-ai agent events directly as Vercel
AI SDK v6 UIMessage stream chunks.

One turn produces multiple phase runs (scoping → discovery → planning →
execution → verification). The v6 protocol requires exactly one
``StartChunk`` and one ``FinishChunk`` + ``DoneChunk`` per stream, so those
turn-level markers are emitted by :mod:`dispatcher` once around the whole
turn; this per-phase emitter strips them so multiple phases can be
concatenated cleanly.

The dispatcher-level ``DataChunk`` emissions (phase telemetry, task
progress, plan artifacts, etc.) come from the same ``get_stream_writer``
channel — they're separate from the agent's pydantic-ai events, so they
don't go through :class:`VercelAIEventStream` at all; they're produced
directly by node / tool code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.ui.vercel_ai._event_stream import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DoneChunk,
    FinishChunk,
    StartChunk,
)

# ``VercelAIEventStream.run_input`` isn't used by ``transform_stream`` —
# it's only referenced by request-parsing helpers we don't invoke. Supply
# a minimal stub so the dataclass constructs.
_PHASE_STUB_INPUT: SubmitMessage = SubmitMessage(
    trigger="submit-message", id="phase", messages=[],
)


@dataclass
class PhaseStreamEmitter:
    """Convert one phase's pydantic-ai agent events into v6 chunks.

    ``VercelAIEventStream.transform_stream`` wraps its output with
    ``StartChunk`` at the front and ``FinishChunk`` + ``DoneChunk`` at the
    tail. Those are turn-level markers in the v6 protocol and can only
    appear once per stream; this class strips them so the dispatcher can
    emit them once around the entire turn.
    """

    message_id: str
    sdk_version: int = 6
    _stream: VercelAIEventStream[Any, Any] = field(init=False)

    def __post_init__(self) -> None:
        self._stream = VercelAIEventStream(
            run_input=_PHASE_STUB_INPUT,
            sdk_version=self.sdk_version,  # type: ignore[arg-type]
            server_message_id=self.message_id,
        )
        self._stream.message_id = self.message_id

    async def chunks(
        self, events: AsyncIterator[Any],
    ) -> AsyncIterator[BaseChunk]:
        """Yield v6 chunks for this phase, minus the turn-level markers."""
        async for chunk in self._stream.transform_stream(events):
            if isinstance(chunk, (StartChunk, FinishChunk, DoneChunk)):
                continue
            yield chunk
