"""A turn that dies leaves a part, so the failure survives a reload.

The live stream shows the failure from the ``error`` chunk, which no reducer
turns into a part. ``data-turn-failed`` is the durable footprint beside it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from pathfinder.ai.conversation import turn_runner as tr
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.tests._support.chunk_log import reduce_chunks_to_messages

_ERROR_TEXT = (
    "The worker running this turn stopped before it finished. "
    "Send the message again to retry."
)


@dataclass
class _StubWriter:
    conversation_id: UUID
    turn_id: UUID
    chunks: list[dict[str, Any]] = field(default_factory=list)

    async def write(self, chunk: dict[str, Any]) -> int:
        self.chunks.append(chunk)
        return len(self.chunks)


class _RaisingGraph:
    """Fails the way a driver fails: partway through the stream."""

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
        yield ("custom", {"chunk": {"type": "text-delta", "id": "t", "delta": "Look"}})
        raise RuntimeError(_ERROR_TEXT)


class _RaisingGraphMidToolCall:
    """Fails while a tool call is open, the way a killed tool call leaves it."""

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
        yield (
            "custom",
            {
                "chunk": {
                    "type": "tool-input-start",
                    "toolCallId": "call-1",
                    "toolName": "search_eda_studies",
                },
            },
        )
        yield (
            "custom",
            {
                "chunk": {
                    "type": "tool-input-available",
                    "toolCallId": "call-1",
                    "toolName": "search_eda_studies",
                    "input": {"limit": 5},
                },
            },
        )
        yield (
            "custom",
            {
                "chunk": {
                    "type": "tool-input-start",
                    "toolCallId": "call-2",
                    "toolName": "list_sites",
                },
            },
        )
        yield (
            "custom",
            {"chunk": {"type": "tool-output-available", "toolCallId": "call-2"}},
        )
        raise RuntimeError(_ERROR_TEXT)


def _body(conversation_id: UUID) -> ChatRequestBody:
    return ChatRequestBody.model_validate(
        {
            "id": str(conversation_id),
            "trigger": "submit-message",
            "messages": [
                {
                    "id": str(uuid4()),
                    "role": "user",
                    "parts": [{"type": "text", "text": "hi"}],
                },
            ],
            "conversationId": str(conversation_id),
            "siteId": "plasmodb",
        },
    )


@pytest.mark.asyncio
async def test_a_raising_graph_writes_the_failure_part_beside_the_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_poll(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(tr, "_watch_for_cancel", _no_poll)

    @dataclass
    class _RuntimeCtx:
        cancel_event: asyncio.Event

    conversation_id = uuid4()
    turn_id = uuid4()
    writer = _StubWriter(conversation_id=conversation_id, turn_id=turn_id)

    result = await tr._drive_graph(
        body=_body(conversation_id),
        graph_input={"turn_message_id": turn_id, "user_id": uuid4()},
        compiled_graph=_RaisingGraph(),
        runtime_context=_RuntimeCtx(cancel_event=asyncio.Event()),
        title_task=None,
        writer=writer,
    )

    assert result.encountered_error is True
    assert [chunk["type"] for chunk in writer.chunks] == [
        "text-delta",
        "error",
        "data-turn-failed",
    ]
    assert writer.chunks[2]["data"] == {"errorText": writer.chunks[1]["errorText"]}


@pytest.mark.asyncio
async def test_a_raising_graph_ends_the_tool_calls_it_left_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_poll(**_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(tr, "_watch_for_cancel", _no_poll)

    @dataclass
    class _RuntimeCtx:
        cancel_event: asyncio.Event

    conversation_id = uuid4()
    turn_id = uuid4()
    writer = _StubWriter(conversation_id=conversation_id, turn_id=turn_id)

    await tr._drive_graph(
        body=_body(conversation_id),
        graph_input={"turn_message_id": turn_id, "user_id": uuid4()},
        compiled_graph=_RaisingGraphMidToolCall(),
        runtime_context=_RuntimeCtx(cancel_event=asyncio.Event()),
        title_task=None,
        writer=writer,
    )

    assert [chunk["type"] for chunk in writer.chunks] == [
        "tool-input-start",
        "tool-input-available",
        "tool-input-start",
        "tool-output-available",
        "tool-output-error",
        "error",
        "data-turn-failed",
    ]
    assert writer.chunks[4]["toolCallId"] == "call-1"
    assert writer.chunks[4]["errorText"] == writer.chunks[5]["errorText"]


def test_the_log_of_a_failed_turn_reduces_to_a_visible_failure() -> None:
    """The chunk log a failed turn leaves rebuilds into three parts."""
    messages = reduce_chunks_to_messages(
        [
            {
                "type": "user-message",
                "message": {"id": "u1", "role": "user", "parts": []},
            },
            {"type": "data-turn-status", "data": {"label": "Queued"}},
            {"type": "start", "messageId": "a1"},
            {"type": "text-start", "id": "t"},
            {
                "type": "text-delta",
                "id": "t",
                "delta": "Looking at PlasmoDB kinases",
            },
            {"type": "text-end", "id": "t"},
            {"type": "error", "errorText": _ERROR_TEXT},
            {"type": "data-turn-failed", "data": {"errorText": _ERROR_TEXT}},
            {"type": "finish", "finishReason": "error"},
            {"type": "done"},
        ],
    )

    parts = messages[1]["parts"]
    assert [part["type"] for part in parts] == [
        "data-turn-status",
        "text",
        "data-turn-failed",
    ]
    assert parts[2]["data"] == {"errorText": _ERROR_TEXT}
