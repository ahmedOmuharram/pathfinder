from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from pathfinder.ai.conversation import turn_runner as tr
from pathfinder.ai.conversation.request_body import ChatRequestBody


@dataclass
class _StubWriter:
    chunks: list[dict[str, Any]]
    conversation_id: Any
    turn_id: Any

    async def write(self, chunk: dict[str, Any]) -> int:
        self.chunks.append(chunk)
        return len(self.chunks)


class _SlowGraph:
    """Yields one custom chunk after a long sleep — long enough to cancel mid-flight."""

    def __init__(self, sleep_for: float = 5.0) -> None:
        self.sleep_for = sleep_for
        self.was_cancelled = False

    def astream(
        self,
        graph_input: dict[str, Any],
        config: dict[str, Any],
        context: Any,
        stream_mode: list[str],
    ) -> AsyncIterator[tuple[str, Any]]:
        del graph_input, config, context, stream_mode
        return self._iter()

    async def _iter(self) -> AsyncIterator[tuple[str, Any]]:
        try:
            await asyncio.sleep(self.sleep_for)
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise
        yield ("custom", {"type": "data-noop"})


@pytest.mark.asyncio
async def test_drive_graph_cancels_mid_call_when_event_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_poll(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(tr, "_watch_for_cancel", _no_poll)

    cancel_event = asyncio.Event()

    @dataclass
    class _RuntimeCtx:
        cancel_event: asyncio.Event

    runtime_context = _RuntimeCtx(cancel_event=cancel_event)
    graph = _SlowGraph(sleep_for=10.0)
    turn_id = uuid4()
    conv_id = uuid4()
    writer_chunks: list[dict[str, Any]] = []
    writer = _StubWriter(chunks=writer_chunks, conversation_id=conv_id, turn_id=turn_id)
    body = ChatRequestBody.model_validate(
        {
            "id": str(conv_id),
            "trigger": "submit-message",
            "messages": [
                {
                    "id": str(uuid4()),
                    "role": "user",
                    "parts": [{"type": "text", "text": "hi"}],
                },
            ],
            "conversationId": str(conv_id),
            "siteId": "plasmodb",
        },
    )

    async def _trigger_cancel() -> None:
        await asyncio.sleep(0.05)
        cancel_event.set()

    trigger = asyncio.create_task(_trigger_cancel())
    drive = asyncio.create_task(
        tr._drive_graph(
            body=body,
            graph_input={
                "turn_message_id": turn_id,
                "user_id": uuid4(),
            },
            compiled_graph=graph,
            runtime_context=runtime_context,
            title_task=None,
            writer=writer,  # type: ignore[arg-type]
        ),
    )

    result = await asyncio.wait_for(drive, timeout=2.0)
    await trigger

    assert result.cancelled is True
    assert graph.was_cancelled is True
