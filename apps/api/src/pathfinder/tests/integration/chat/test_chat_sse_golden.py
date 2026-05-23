"""Golden-snapshot test for one full chat turn's SSE stream.

Posts a fixed prompt to ``POST /api/v1/chat`` with the mock LLM provider,
drains the in-memory procrastinate worker so the turn finishes, parses the
streamed response into the ordered list of typed chunks, redacts volatile
fields (ids/timestamps/UUIDs), and compares the result against a checked-in
fixture. Any reorder/drop/add/reshape in the LangGraph dispatcher pipeline
fails this test loudly.

Re-record with::

    PATHFINDER_RECORD_GOLDEN=1 uv run pytest \\
        src/pathfinder/tests/integration/chat/test_chat_sse_golden.py -v
"""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.tasks import ensure_registered
from pathfinder.platform.security import create_user_token
from pathfinder.tests.integration.chat._helpers import parse_sse_body, redact

pytestmark = pytest.mark.asyncio

_FIXTURE_PATH = (
    Path(__file__).parent / "_fixtures" / "chat_sse_golden_simple_turn.json"
)

# The fixed prompt drives the mock supervisor into the ``question`` branch:
# a single supervisor decision + a turn-qa data chunk + finish/done. No
# phase nodes run. Keeps the snapshot small and bit-stable.
_PROMPT = "hi"

# The full set of chunk ``type`` values the dispatcher is allowed to emit on
# this turn. Any chunk type outside this set indicates new behavior the
# golden must explicitly cover — re-record the fixture and update this set.
_ALLOWED_CHUNK_TYPES: frozenset[str] = frozenset({
    "start",
    "finish",
    "done",
    "start-step",
    "finish-step",
    "text-start",
    "text-delta",
    "text-end",
    "tool-input-start",
    "tool-input-delta",
    "tool-input-available",
    "tool-output-available",
    "data-sub-agent-call",
    "data-ledger-update",
    "data-turn-usage",
    "data-conversation-title",
    "message-metadata",
})


@pytest.fixture
async def in_memory_jobs() -> AsyncIterator[InMemoryConnector]:
    original_connector = procrastinate_app.connector
    original_jm_connector = procrastinate_app.job_manager.connector
    connector = InMemoryConnector()
    procrastinate_app.connector = connector
    procrastinate_app.job_manager.connector = connector
    ensure_registered()
    try:
        yield connector
    finally:
        procrastinate_app.connector = original_connector
        procrastinate_app.job_manager.connector = original_jm_connector


async def _drain_chat_jobs() -> None:
    async with procrastinate_app.open_async():
        await procrastinate_app.run_worker_async(
            queues=["chat_turn"],
            wait=False,
            listen_notify=False,
            install_signal_handlers=False,
        )


async def _wait_until_enqueued(connector: InMemoryConnector) -> None:
    while True:
        if any(
            j["task_name"] == "chat_turn:run"
            for j in connector.jobs.values()
        ):
            return
        await asyncio.sleep(0.02)


def _post_body(conv_id: UUID, prompt: str) -> dict[str, Any]:
    msg_id = str(uuid4())
    return {
        "trigger": "submit-message",
        "id": msg_id,
        "messages": [
            {
                "id": msg_id,
                "role": "user",
                "parts": [{"type": "text", "text": prompt}],
            },
        ],
        "conversationId": str(conv_id),
        "siteId": "plasmodb",
    }


async def _run_turn_and_collect(
    app: FastAPI, user_id: UUID, in_memory_jobs: InMemoryConnector,
) -> list[dict[str, Any]]:
    conv_id = uuid4()
    token = create_user_token(user_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post_task = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=_post_body(conv_id, _PROMPT),
                timeout=30.0,
            ),
        )
        await asyncio.wait_for(_wait_until_enqueued(in_memory_jobs), timeout=5.0)
        await _drain_chat_jobs()
        response = await asyncio.wait_for(post_task, timeout=30.0)

    if response.status_code != 200:
        msg = (
            f"chat returned {response.status_code}; body={response.text[:500]!r}"
        )
        raise AssertionError(msg)
    raw_chunks = parse_sse_body(response.text)
    return [redact(c) for c in raw_chunks]


def _load_fixture() -> list[dict[str, Any]]:
    raw = json.loads(_FIXTURE_PATH.read_text())
    if not isinstance(raw, list):
        msg = f"fixture root must be a list, got {type(raw).__name__}"
        raise TypeError(msg)
    return raw


def _save_fixture(chunks: list[dict[str, Any]]) -> None:
    _FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FIXTURE_PATH.write_text(
        json.dumps(chunks, indent=2, sort_keys=True) + "\n",
    )


def _diff_message(
    actual: list[dict[str, Any]], expected: list[dict[str, Any]],
) -> str:
    actual_json = json.dumps(actual, indent=2, sort_keys=True)
    expected_json = json.dumps(expected, indent=2, sort_keys=True)
    return (
        "SSE golden mismatch.\n"
        f"--- expected ({_FIXTURE_PATH}) ---\n{expected_json}\n"
        f"--- actual ---\n{actual_json}\n"
        "\nIf the change is intentional, re-record the fixture:\n"
        "  PATHFINDER_RECORD_GOLDEN=1 uv run pytest "
        "src/pathfinder/tests/integration/chat/test_chat_sse_golden.py -v"
    )


async def test_chat_sse_golden_snapshot_simple_turn(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """One simple-turn SSE stream, frozen as a golden chunk list."""
    del patch_app_db_engine, db_cleaner
    chunks = await _run_turn_and_collect(app, authed_user_id, in_memory_jobs)

    if os.environ.get("PATHFINDER_RECORD_GOLDEN") == "1":
        _save_fixture(chunks)
        return

    if not _FIXTURE_PATH.is_file():
        msg = (
            f"golden fixture missing at {_FIXTURE_PATH}. "
            "Re-record with: PATHFINDER_RECORD_GOLDEN=1 uv run pytest "
            "src/pathfinder/tests/integration/chat/test_chat_sse_golden.py -v"
        )
        raise AssertionError(msg)

    expected = _load_fixture()

    types = [c.get("type") for c in chunks]
    unknown = [t for t in types if t not in _ALLOWED_CHUNK_TYPES]
    assert unknown == [], (
        f"chunks emitted unknown type(s) {unknown}; "
        f"add to _ALLOWED_CHUNK_TYPES or fix the dispatcher. all types={types}"
    )
    assert types.count("start") == 1
    assert types.count("done") == 1
    assert types[0] == "start"
    assert types[-1] == "done"

    assert chunks == expected, _diff_message(chunks, expected)
