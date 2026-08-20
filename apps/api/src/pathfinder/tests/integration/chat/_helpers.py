"""Helpers for the chat turn integration tests.

Three responsibilities only:
- drive one turn against ``/api/v1/chat`` (request body, wait for the
  deferred job, run it);
- parse the raw SSE response body emitted by ``/api/v1/chat`` into a list
  of typed chunk dicts (one per ``data:`` line, ``[DONE]`` excluded);
- redact volatile fields (ids, timestamps, UUIDs) so the snapshot stays
  stable across runs.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from procrastinate.testing import InMemoryConnector

from pathfinder.jobs.app import procrastinate_app

_CHAT_TURN_TASK = "chat_turn:run"

_VOLATILE_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "run_id",
        "runId",
        "chat_id",
        "chatId",
        "message_id",
        "messageId",
        "step_id",
        "stepId",
        "task_id",
        "taskId",
        "tool_call_id",
        "toolCallId",
        "trace_id",
        "traceId",
        "created_at",
        "createdAt",
        "updated_at",
        "updatedAt",
        "started_at",
        "startedAt",
        "finished_at",
        "finishedAt",
        "timestamp",
    }
)

_REDACTED = "<REDACTED>"

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_GENERIC_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def chat_post_body(conversation_id: UUID, prompt: str) -> dict[str, Any]:
    """Build the ``POST /api/v1/chat`` body for one user message."""
    message_id = str(uuid4())
    return {
        "trigger": "submit-message",
        "id": message_id,
        "messages": [
            {
                "id": message_id,
                "role": "user",
                "parts": [{"type": "text", "text": prompt}],
            },
        ],
        "conversationId": str(conversation_id),
        "siteId": "plasmodb",
    }


def chat_turn_jobs(connector: InMemoryConnector) -> list[dict[str, Any]]:
    """Return the deferred chat-turn jobs, oldest first."""
    return [
        job for job in connector.jobs.values() if job["task_name"] == _CHAT_TURN_TASK
    ]


async def wait_until_chat_turn_deferred(connector: InMemoryConnector) -> None:
    while True:
        if chat_turn_jobs(connector):
            return
        await asyncio.sleep(0.02)


async def run_deferred_chat_turns() -> None:
    """Run every queued chat turn to completion, then return."""
    async with procrastinate_app.open_async():
        await procrastinate_app.run_worker_async(
            queues=["chat_turn"],
            wait=False,
            listen_notify=False,
            install_signal_handlers=False,
        )


def parse_sse_body(body: str) -> list[dict[str, Any]]:
    """Parse a raw SSE body into an ordered list of decoded chunk dicts.

    Each event is ``id: <n>\\ndata: <json or [DONE]>\\n\\n``. The literal
    ``[DONE]`` payload (emitted for the AI SDK ``DoneChunk``) is rehydrated
    into ``{"type": "done"}`` so the chunk list keeps the original
    framing markers.
    """
    chunks: list[dict[str, Any]] = []
    for raw_block in body.split("\n\n"):
        block = raw_block.strip("\n")
        if not block:
            continue
        data_line: str | None = None
        for line in block.splitlines():
            if line.startswith("data:"):
                data_line = line[len("data:") :].strip()
                break
        if data_line is None:
            continue
        if data_line == "[DONE]":
            chunks.append({"type": "done"})
            continue
        parsed = json.loads(data_line)
        if not isinstance(parsed, dict):
            msg = f"non-object SSE payload: {parsed!r}"
            raise TypeError(msg)
        chunks.append(parsed)
    return chunks


def _looks_iso8601(value: str) -> bool:
    if "T" not in value or len(value) < 16:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _looks_uuid(value: str) -> bool:
    return bool(_UUID4_RE.match(value) or _GENERIC_UUID_RE.match(value))


def _redact_string(value: str) -> str:
    if _looks_uuid(value) or _looks_iso8601(value):
        return _REDACTED
    return value


def redact(node: Any, *, parent_key: str | None = None) -> Any:
    """Recursively redact volatile fields. Replaces:
    - any value at a key in :data:`_VOLATILE_KEYS` with ``"<REDACTED>"``;
    - any UUID-looking string anywhere with ``"<REDACTED>"``;
    - any ISO-8601 timestamp string anywhere with ``"<REDACTED>"``.
    Other values pass through.
    """
    del parent_key
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            if k in _VOLATILE_KEYS:
                out[k] = _REDACTED
            else:
                out[k] = redact(v, parent_key=k)
        return out
    if isinstance(node, list):
        return [redact(item) for item in node]
    if isinstance(node, str):
        return _redact_string(node)
    return node
