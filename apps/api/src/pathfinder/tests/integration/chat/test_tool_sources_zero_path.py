"""A spec that declares no tool sources opens no session on its turn."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector

from pathfinder.ai.conversation import turn_runner
from pathfinder.platform.security import create_user_token
from pathfinder.tests.integration.chat._helpers import (
    chat_post_body,
    parse_sse_body,
    run_deferred_chat_turns,
    wait_until_chat_turn_deferred,
)

_OK = 200


class _NeverResolved:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        msg = "a zero-source turn must not construct ResolvedToolSources"
        raise AssertionError(msg)


async def test_a_zero_source_turn_never_builds_a_resolver(
    app: FastAPI,
    patch_app_db_engine: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
    monkeypatch: Any,
) -> None:
    del patch_app_db_engine, signed_in_to_veupathdb
    monkeypatch.setattr(turn_runner, "ResolvedToolSources", _NeverResolved)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": create_user_token(authed_user_id)},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=chat_post_body(uuid4(), "hi"),
                timeout=60.0,
            ),
        )
        await asyncio.wait_for(
            wait_until_chat_turn_deferred(in_memory_jobs),
            timeout=30.0,
        )
        await run_deferred_chat_turns()
        response = await asyncio.wait_for(post, timeout=60.0)

    assert response.status_code == _OK, response.text
    chunks = parse_sse_body(response.text)
    types = [chunk["type"] for chunk in chunks]
    assert "error" not in types
    assert types[-2:] == ["finish", "done"]
