"""A turn that asks for no strategy leaves none behind.

Two messages through the real dispatcher on the deterministic provider: a
request to remember a preference, and a bare statement of what the user works
on. Neither may reach a sub-agent or a strategy snapshot.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector

from pathfinder.platform.security import create_user_token
from pathfinder.tests.integration.chat._helpers import (
    chat_post_body,
    parse_sse_body,
    run_deferred_chat_turns,
    wait_until_chat_turn_deferred,
)

_DEADLOCK_CEILING_SECONDS = 120.0

_REMEMBER_PROMPT = (
    "Please remember for future sessions: I always work with P. falciparum 3D7."
)
_CONTEXT_PROMPT = "I'm investigating virulence factors in Leishmania major"


async def _turn_chunks(
    app: FastAPI,
    user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    prompt: str,
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
                json=chat_post_body(conv_id, prompt),
                timeout=30.0,
            ),
        )
        await asyncio.wait_for(
            wait_until_chat_turn_deferred(in_memory_jobs),
            timeout=_DEADLOCK_CEILING_SECONDS,
        )
        await run_deferred_chat_turns()
        response = await asyncio.wait_for(
            post_task,
            timeout=_DEADLOCK_CEILING_SECONDS,
        )
    assert response.status_code == 200, response.text[:500]
    return parse_sse_body(response.text)


def _tool_names(chunks: list[dict[str, Any]]) -> list[str]:
    return [
        str(chunk["toolName"])
        for chunk in chunks
        if chunk.get("type") == "tool-input-available"
    ]


def _types(chunks: list[dict[str, Any]]) -> list[str]:
    return [str(chunk.get("type")) for chunk in chunks]


async def test_a_remember_request_stores_and_builds_nothing(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, db_cleaner, signed_in_to_veupathdb
    chunks = await _turn_chunks(app, authed_user_id, in_memory_jobs, _REMEMBER_PROMPT)

    assert "remember" in _tool_names(chunks)
    assert "frame_problem" not in _tool_names(chunks)
    assert "data-graph-snapshot" not in _types(chunks)


async def test_a_context_statement_answers_in_prose(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, db_cleaner, signed_in_to_veupathdb
    chunks = await _turn_chunks(app, authed_user_id, in_memory_jobs, _CONTEXT_PROMPT)

    assert "data-sub-agent-call" not in _types(chunks)
    assert "data-graph-snapshot" not in _types(chunks)
    text = "".join(
        str(chunk.get("delta", ""))
        for chunk in chunks
        if chunk.get("type") == "text-delta"
    )
    assert "Want me to" in text
