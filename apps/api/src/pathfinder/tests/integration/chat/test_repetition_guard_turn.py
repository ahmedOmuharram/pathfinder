"""A PathFinder turn that repeats one catalog read is stopped by the guard.

The scripted FRAME arc asks for the same listing on every step. The guard
refuses the third identical call and ends the sub-agent's pass on the fourth,
so the turn finishes with a reply instead of spending its whole budget.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx
from assistant_core.capabilities.repetition_guard import (
    DEFAULT_REPETITION_THRESHOLD,
    REPETITION_MARKER,
)
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector

from pathfinder.platform.security import create_user_token
from pathfinder.tests.integration.chat._helpers import (
    chat_post_body,
    parse_sse_body,
    run_deferred_chat_turns,
    wait_until_chat_turn_deferred,
)

_PROMPT = "read the catalog again and again"
_LOOPING_TOOL = "list_searches"
_OK = 200


async def _turn(
    app: FastAPI,
    user_id: UUID,
    in_memory_jobs: InMemoryConnector,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": create_user_token(user_id)},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=chat_post_body(uuid4(), _PROMPT),
                timeout=60.0,
            ),
        )
        await asyncio.wait_for(
            wait_until_chat_turn_deferred(in_memory_jobs),
            timeout=10.0,
        )
        await run_deferred_chat_turns()
        response = await asyncio.wait_for(post, timeout=60.0)
    assert response.status_code == _OK, response.text
    return parse_sse_body(response.text)


def _inner_steps(chunks: list[dict[str, Any]], tool: str) -> list[dict[str, Any]]:
    return [
        chunk["data"]
        for chunk in chunks
        if chunk["type"] == "data-sub-agent-step"
        and chunk["data"].get("toolName") == tool
    ]


async def test_the_repeated_catalog_read_is_refused_inside_frame(
    app: FastAPI,
    patch_app_db_engine: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, signed_in_to_veupathdb

    chunks = await _turn(app, authed_user_id, in_memory_jobs)

    refused = [
        step
        for step in _inner_steps(chunks, _LOOPING_TOOL)
        if REPETITION_MARKER in (step.get("resultSummary") or "")
    ]
    assert refused
    assert refused[0]["state"] == "completed"


async def test_the_loop_stops_rather_than_spending_the_phase_budget(
    app: FastAPI,
    patch_app_db_engine: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, signed_in_to_veupathdb

    chunks = await _turn(app, authed_user_id, in_memory_jobs)

    started = [
        step
        for step in _inner_steps(chunks, _LOOPING_TOOL)
        if step["state"] == "started"
    ]
    assert len(started) == DEFAULT_REPETITION_THRESHOLD + 1


async def test_the_stopped_turn_still_answers_the_user(
    app: FastAPI,
    patch_app_db_engine: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, signed_in_to_veupathdb

    chunks = await _turn(app, authed_user_id, in_memory_jobs)

    types = [chunk["type"] for chunk in chunks]
    text = "".join(c.get("delta", "") for c in chunks if c["type"] == "text-delta")
    assert "error" not in types
    assert types[-2:] == ["finish", "done"]
    assert text
