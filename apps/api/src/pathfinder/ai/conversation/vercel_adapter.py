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

# TODO(upstream): remove once pydantic-ai exposes
# ``VERCEL_AI_DSP_HEADERS`` from ``pydantic_ai.ui.vercel_ai`` (currently
# only available via the private ``_event_stream`` module).
VERCEL_AI_DSP_HEADERS: dict[str, str] = {
    "x-vercel-ai-ui-message-stream": "v1",
}

_PHASE_STUB_INPUT: SubmitMessage = SubmitMessage(
    trigger="submit-message", id="phase", messages=[],
)


@dataclass
class PinnedVercelAIEventStream(VercelAIEventStream[Any, Any]):
    # TODO(upstream): file against pydantic-ai. Base class uses a single
    # mutable ``self.message_id`` so an interleaved ``ThinkingPart`` between
    # a TextPart's start and its first delta routes the delta with the
    # wrong id (validator rejects:
    # ``Received reasoning-delta for missing reasoning part with ID ...``).
    # Suggested fix upstream: key id by ``event.index`` instead of
    # ``self.message_id``. Once fixed, delete this class and use
    # ``VercelAIEventStream`` directly in ``PhaseStreamEmitter``.

    _index_to_message_id: dict[int, str] = field(default_factory=dict, init=False)

    async def handle_part_start(
        self, event: PartStartEvent,
    ) -> AsyncIterator[BaseChunk]:
        async for chunk in super().handle_part_start(event):
            yield chunk
        if isinstance(event.part, (TextPart, ThinkingPart)):
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
    # Strips turn-level ``StartChunk``/``FinishChunk``/``DoneChunk`` markers
    # so multiple phase runs can be concatenated into one v6 stream.

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
        async for chunk in self._stream.transform_stream(events):
            if isinstance(chunk, (StartChunk, FinishChunk, DoneChunk)):
                continue
            yield chunk
