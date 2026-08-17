"""Every mutating conversation-scoped route refuses a non-owner.

The matrix is explicit so a reviewer can read what is covered, and it is
cross-checked against ``app.routes`` so a new route cannot join the app
without joining the matrix.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from procrastinate.testing import InMemoryConnector
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.scratchpad.models import NoteCreate
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories.scratchpad import ScratchpadRepository
from pathfinder.tests.integration.http.conftest import (
    chat_body,
    client_for,
    make_user,
)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ALLOWED_STATUSES = frozenset({403, 404})
_STREAM_TIMEOUT_SECONDS = 15.0

# Names that address a conversation, whether in the path or in the JSON body.
_CONVERSATION_KEYS = frozenset(
    {
        "conversation_id",
        "conversationId",
        "chat_id",
        "chatId",
        "strategy_id",
        "strategyId",
    }
)

# Langfuse telemetry: the id is an analytics label, and the route reads and
# writes no PathFinder-owned resource.
_NOT_CONVERSATION_SCOPED = frozenset({("POST", "/api/v1/feedback/actions")})


@dataclass(frozen=True)
class _Case:
    method: str
    route: str
    url: str
    body: dict[str, Any] | None = None


def _cases(conversation_id: UUID, note_id: str) -> tuple[_Case, ...]:
    conv = str(conversation_id)
    base = f"/api/v1/conversations/{conv}"
    notes = f"{base}/scratchpad/notes/{note_id}"
    site = "?siteId=plasmodb"
    return (
        _Case("POST", "/api/v1/chat", "/api/v1/chat", chat_body(conversation_id)),
        _Case(
            "PATCH",
            "/api/v1/conversations/{strategyId:uuid}",
            base,
            {"name": "renamed by an intruder"},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{strategyId:uuid}/fork",
            f"{base}/fork",
            {"fromMessageId": str(uuid4())},
        ),
        _Case("DELETE", "/api/v1/conversations/{strategyId:uuid}", base),
        _Case(
            "POST",
            "/api/v1/conversations/{strategyId:uuid}/restore",
            f"{base}/restore",
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id}/begin",
            f"{base}/begin",
            {"siteId": "plasmodb"},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{strategyId:uuid}/operations",
            f"{base}/operations{site}",
            {"op": {"kind": "updateStrategyMeta", "name": "renamed by an intruder"}},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/open",
            "/api/v1/conversations/open",
            {"conversationId": conv, "siteId": "plasmodb"},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id}/dismiss",
            f"{base}/dismiss",
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id}/duplicate",
            f"{base}/duplicate",
        ),
        _Case(
            "PATCH",
            "/api/v1/conversations/{conversation_id}/scratchpad/notes/{note_id}",
            notes,
            {"pinned": True},
        ),
        _Case(
            "DELETE",
            "/api/v1/conversations/{conversation_id}/scratchpad/notes/{note_id}",
            notes,
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id}/revert-to-message",
            f"{base}/revert-to-message",
            {"messageId": str(uuid4())},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id:uuid}/save-substrategy",
            f"{base}/save-substrategy{site}",
            {"stepId": "root", "name": "stolen subtree"},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id:uuid}/insert-saved",
            f"{base}/insert-saved{site}",
            {"targetStepId": "root", "savedWdkStrategyId": 1},
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id}/turns/{turn_id}/cancel",
            f"{base}/turns/{uuid4()}/cancel",
        ),
        _Case(
            "POST",
            "/api/v1/conversations/{conversation_id}/cancel",
            f"{base}/cancel",
        ),
        _Case(
            "POST",
            "/api/v1/eval/strategy-gene-ids",
            "/api/v1/eval/strategy-gene-ids",
            {"strategyId": conv, "siteId": "plasmodb"},
        ),
    )


def _path_keys(path: str) -> set[str]:
    return {token.split(":")[0] for token in re.findall(r"\{([^}]+)\}", path)}


def _body_keys(route: APIRoute) -> set[str]:
    body = route.body_field
    if body is None:
        return set()
    annotation = body.field_info.annotation
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return set(annotation.model_fields)
    return set()


def _conversation_scoped_routes(app: FastAPI) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        keys = (_path_keys(route.path) | _body_keys(route)) & _CONVERSATION_KEYS
        if not keys:
            continue
        found |= {
            (method, route.path)
            for method in route.methods & _MUTATING_METHODS
            if (method, route.path) not in _NOT_CONVERSATION_SCOPED
        }
    return found


def _registered_routes(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


async def _status_for(client: httpx.AsyncClient, case: _Case) -> int | None:
    """Return the status code, or None when the route streams instead."""
    call = asyncio.create_task(
        client.request(case.method, case.url, json=case.body, timeout=60.0),
    )
    try:
        response = await asyncio.wait_for(
            asyncio.shield(call),
            timeout=_STREAM_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        call.cancel()
        await asyncio.gather(call, return_exceptions=True)
        return None
    return response.status_code


@pytest.fixture
async def owned_resources(db_session: AsyncSession) -> tuple[UUID, str]:
    """One conversation owned by a fresh user, and one scratchpad note in it."""
    owner = await make_user(db_session)
    conversation = Conversation(
        user_id=owner.id,
        site_id="plasmodb",
        name="Owner kinases",
        experiment_id=None,
    )
    db_session.add(conversation)
    await db_session.flush()
    note = await ScratchpadRepository(db_session).create(
        conversation_id=conversation.id,
        data=NoteCreate(title="t", summary="s", body="b"),
    )
    await db_session.commit()
    return conversation.id, note.id


def test_every_case_names_a_route_the_app_still_serves(app: FastAPI) -> None:
    registered = _registered_routes(app)
    missing = [
        (case.method, case.route)
        for case in _cases(uuid4(), "note-1")
        if (case.method, case.route) not in registered
    ]
    assert missing == [], (
        f"authz matrix names routes the app no longer serves: {missing}"
    )


def test_every_conversation_scoped_mutating_route_is_in_the_matrix(
    app: FastAPI,
) -> None:
    covered = {(case.method, case.route) for case in _cases(uuid4(), "note-1")}
    uncovered = sorted(_conversation_scoped_routes(app) - covered)
    assert uncovered == [], (
        f"conversation-scoped mutating routes missing from the authz matrix: "
        f"{uncovered}"
    )


async def test_begin_refuses_a_non_owner_with_a_stable_problem_code(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    owned_resources: tuple[UUID, str],
) -> None:
    """Pins the refusal the begin route surfaces, wherever it is raised."""
    del patch_app_db_engine
    conversation_id, _note_id = owned_resources
    intruder = await make_user(db_session)

    async with client_for(app, intruder.id) as client:
        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/begin",
            json={"siteId": "plasmodb"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "STRATEGY_NOT_FOUND"


async def test_a_non_owner_is_refused_by_every_route(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    owned_resources: tuple[UUID, str],
    in_memory_jobs: InMemoryConnector,
) -> None:
    del patch_app_db_engine, in_memory_jobs
    conversation_id, note_id = owned_resources
    intruder = await make_user(db_session)

    offenders: list[str] = []
    async with client_for(app, intruder.id) as client:
        for case in _cases(conversation_id, note_id):
            status = await _status_for(client, case)
            if status not in _ALLOWED_STATUSES:
                served = "an open SSE stream" if status is None else str(status)
                offenders.append(f"{case.method} {case.url} -> {served}")

    assert offenders == [], (
        "routes that served a non-owner instead of 403/404: " + "; ".join(offenders)
    )
