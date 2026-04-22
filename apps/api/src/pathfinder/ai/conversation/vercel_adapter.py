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

``PinnedVercelAIEventStream`` below fixes an upstream correctness bug in
``pydantic_ai.ui.vercel_ai._event_stream.VercelAIEventStream``: the base
class keeps a single mutable ``self.message_id`` that every ``handle_*_``
method mutates and reads, so a ``PartDeltaEvent`` / ``PartEndEvent`` for
an earlier part is routed with whatever id the *most recent* part-start
minted. That produces ``reasoning-delta`` chunks whose id was never
``reasoning-start``'d on the frontend, which the AI SDK v6 protocol
validator rejects with
``Received reasoning-delta for missing reasoning part with ID ...``.
We pin ``self.message_id`` to the per-index id around every delta/end
dispatch so each part's chunks are coherent regardless of vendor
ordering.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic_ai.messages import (
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    ThinkingPart,
)
from pydantic_ai.ui.vercel_ai._event_stream import VercelAIEventStream
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DoneChunk,
    FinishChunk,
    StartChunk,
)

_PHASE_STUB_INPUT: SubmitMessage = SubmitMessage(
    trigger="submit-message", id="phase", messages=[],
)


@dataclass
class PinnedVercelAIEventStream(VercelAIEventStream[Any, Any]):
    """``VercelAIEventStream`` that pins the message id to the originating part.

    The base class uses ``self.message_id`` as an implicit "current" pointer
    that every ``handle_*_`` method mutates. When parts arrive out of order
    (or when interleaved-thinking shifts ``self.message_id`` between a
    thinking part's start and its own delta), downstream reasoning/text
    chunks reference an id that was never opened. We maintain an
    index -> id map populated on each part-start and restore
    ``self.message_id`` to the part's own id before dispatching delta/end.
    """

    _index_to_message_id: dict[int, str] = field(default_factory=dict, init=False)

    async def handle_part_start(
        self, event: PartStartEvent,
    ) -> AsyncIterator[BaseChunk]:
        async for chunk in super().handle_part_start(event):
            yield chunk
        if isinstance(event.part, (TextPart, ThinkingPart)):
            # After super() returns, ``self.message_id`` is the id
            # associated with this part (a freshly minted one for non-
            # follows_text starts, or the previous text's id when
            # ``follows_text=True`` reuses it).
            self._index_to_message_id[event.index] = self.message_id

    async def handle_part_delta(
        self, event: PartDeltaEvent,
    ) -> AsyncIterator[BaseChunk]:
        pinned = self._index_to_message_id.get(event.index)
        if pinned is None:
            async for chunk in super().handle_part_delta(event):
                yield chunk
            return
        saved = self.message_id
        self.message_id = pinned
        try:
            async for chunk in super().handle_part_delta(event):
                yield chunk
        finally:
            self.message_id = saved

    async def handle_part_end(
        self, event: PartEndEvent,
    ) -> AsyncIterator[BaseChunk]:
        pinned = self._index_to_message_id.get(event.index)
        if pinned is None:
            async for chunk in super().handle_part_end(event):
                yield chunk
            return
        saved = self.message_id
        self.message_id = pinned
        try:
            async for chunk in super().handle_part_end(event):
                yield chunk
        finally:
            self.message_id = saved


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
    sdk_version: Literal[5, 6] = 6
    _stream: PinnedVercelAIEventStream = field(init=False)

    def __post_init__(self) -> None:
        self._stream = PinnedVercelAIEventStream(
            run_input=_PHASE_STUB_INPUT,
            sdk_version=self.sdk_version,
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
