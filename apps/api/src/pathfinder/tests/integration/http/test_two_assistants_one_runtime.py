"""Two assistants answer through one runtime, each under its own architecture.

PathFinder needs a registered VEuPathDB login and runs its lead graph; site
help needs no WDK identity at all and runs a single agent. Both are dispatched,
worked and streamed by the same pipeline.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from assistant_core.persistence.models import Conversation, Message
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from procrastinate.testing import InMemoryConnector
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import pathfinder.assistants.registry as registry_mod
from pathfinder.assistants.registry import get_assistant_registry
from pathfinder.assistants.site_help.mock import SITES_REPLY
from pathfinder.tests.integration.chat._helpers import (
    chat_post_body,
    chat_turn_jobs,
    parse_sse_body,
    run_deferred_chat_turns,
    wait_until_chat_turn_deferred,
)
from pathfinder.tests.integration.http._confirming_assistant import (
    CONFIRM_CALL_ID,
    CONFIRM_PROMPT,
    CONFIRM_TOOL,
    CONFIRMED_REPLY,
    build_confirming_spec,
)
from pathfinder.tests.integration.http.conftest import client_for, make_user
from pathfinder.tests.integration.http.test_wdk_login_required import (
    LOGIN_CODE,
    LOGIN_DETAIL,
    LOGIN_TITLE,
)

_UNAUTHORIZED = 401
_SITE_HELP = "site_help"
_SITES_PROMPT = "which sites can I search"


async def _turn(
    app: FastAPI,
    user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    *,
    conversation_id: UUID,
    prompt: str,
    assistant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Drive one turn end to end and return its streamed chunks."""
    body = chat_post_body(conversation_id, prompt)
    if assistant_id is not None:
        body["assistantId"] = assistant_id
    return await _turn_with_body(app, user_id, in_memory_jobs, body=body)


async def _turn_with_body(
    app: FastAPI,
    user_id: UUID,
    in_memory_jobs: InMemoryConnector,
    *,
    body: dict[str, Any],
) -> list[dict[str, Any]]:
    queued = len(chat_turn_jobs(in_memory_jobs))
    async with client_for(app, user_id) as client:
        post = asyncio.create_task(
            client.post("/api/v1/chat", json=body, timeout=60.0),
        )
        await asyncio.wait_for(
            wait_until_chat_turn_deferred(in_memory_jobs, queued),
            timeout=10.0,
        )
        await run_deferred_chat_turns()
        response = await asyncio.wait_for(post, timeout=60.0)
    assert response.status_code == 200, response.text
    return parse_sse_body(response.text)


async def _assistant_of(
    session_maker: async_sessionmaker[AsyncSession],
    conversation_id: UUID,
) -> str | None:
    async with session_maker() as session:
        return await session.scalar(
            select(Conversation.assistant_id).where(
                Conversation.id == conversation_id,
            ),
        )


def _text(chunks: list[dict[str, Any]]) -> str:
    return "".join(c.get("delta", "") for c in chunks if c["type"] == "text-delta")


@pytest.fixture
def confirming_assistant(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Serve site help's id from an assistant whose one tool needs approval."""
    monkeypatch.setattr(registry_mod, "build_site_help_spec", build_confirming_spec)
    get_assistant_registry.cache_clear()
    yield
    get_assistant_registry.cache_clear()


def _approval_body(
    conversation_id: UUID,
    *,
    approved: bool,
    reason: str | None = None,
) -> dict[str, Any]:
    """The body the client sends when the user answers an approval card."""
    approval: dict[str, Any] = {
        "id": CONFIRM_CALL_ID,
        "approved": approved,
    }
    if reason is not None:
        approval["reason"] = reason
    message_id = str(uuid4())
    return {
        "trigger": "submit-message",
        "id": message_id,
        "messages": [
            {
                "id": message_id,
                "role": "assistant",
                "parts": [
                    {
                        "type": f"tool-{CONFIRM_TOOL}",
                        "toolCallId": CONFIRM_CALL_ID,
                        "state": "approval-responded",
                        "input": {"geneSetId": "kinase-candidates"},
                        "approval": approval,
                    },
                ],
            },
        ],
        "conversationId": str(conversation_id),
        "siteId": "plasmodb",
        "assistantId": _SITE_HELP,
    }


async def test_a_one_agent_assistant_asks_the_user_before_it_runs_the_tool(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    in_memory_jobs: InMemoryConnector,
    confirming_assistant: None,
) -> None:
    del patch_app_db_engine, confirming_assistant
    owner = await make_user(db_session)

    chunks = await _turn(
        app,
        owner.id,
        in_memory_jobs,
        conversation_id=uuid4(),
        prompt=CONFIRM_PROMPT,
        assistant_id=_SITE_HELP,
    )

    types = [c["type"] for c in chunks]
    requests = [c for c in chunks if c["type"] == "tool-approval-request"]
    assert [c["toolCallId"] for c in requests] == [CONFIRM_CALL_ID]
    assert "error" not in types
    assert types[-2:] == ["finish", "done"]


async def test_the_answered_card_runs_the_tool_on_the_next_request(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    in_memory_jobs: InMemoryConnector,
    confirming_assistant: None,
) -> None:
    del patch_app_db_engine, confirming_assistant
    owner = await make_user(db_session)
    conversation_id = uuid4()
    await _turn(
        app,
        owner.id,
        in_memory_jobs,
        conversation_id=conversation_id,
        prompt=CONFIRM_PROMPT,
        assistant_id=_SITE_HELP,
    )

    chunks = await _turn_with_body(
        app,
        owner.id,
        in_memory_jobs,
        body=_approval_body(conversation_id, approved=True),
    )

    outputs = [c for c in chunks if c["type"] == "tool-output-available"]
    assert [c["toolCallId"] for c in outputs] == [CONFIRM_CALL_ID]
    assert _text(chunks) == CONFIRMED_REPLY


async def test_a_refused_card_denies_the_call_over_the_same_route(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    in_memory_jobs: InMemoryConnector,
    confirming_assistant: None,
) -> None:
    del patch_app_db_engine, confirming_assistant
    owner = await make_user(db_session)
    conversation_id = uuid4()
    await _turn(
        app,
        owner.id,
        in_memory_jobs,
        conversation_id=conversation_id,
        prompt=CONFIRM_PROMPT,
        assistant_id=_SITE_HELP,
    )

    chunks = await _turn_with_body(
        app,
        owner.id,
        in_memory_jobs,
        body=_approval_body(conversation_id, approved=False, reason="no thanks"),
    )

    denials = [c for c in chunks if c["type"] == "tool-output-denied"]
    assert [c["toolCallId"] for c in denials] == [CONFIRM_CALL_ID]
    assert [c for c in chunks if c["type"] == "tool-output-available"] == []


async def test_a_site_help_turn_runs_without_any_wdk_login(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
    in_memory_jobs: InMemoryConnector,
) -> None:
    """No WDK token, no identity override: the assistant declares no gate."""
    del patch_app_db_engine
    owner = await make_user(db_session)
    conversation_id = uuid4()

    chunks = await _turn(
        app,
        owner.id,
        in_memory_jobs,
        conversation_id=conversation_id,
        prompt=_SITES_PROMPT,
        assistant_id=_SITE_HELP,
    )

    types = [c["type"] for c in chunks]
    assert types[-2:] == ["finish", "done"]
    assert await _assistant_of(session_maker, conversation_id) == _SITE_HELP


async def test_the_same_request_against_pathfinder_still_needs_a_login(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """PathFinder's refusal is unchanged, on the same route, with the same body."""
    del patch_app_db_engine, in_memory_jobs
    owner = await make_user(db_session)
    body = chat_post_body(uuid4(), _SITES_PROMPT)

    async with client_for(app, owner.id) as client:
        response = await client.post("/api/v1/chat", json=body, timeout=30.0)

    assert response.status_code == _UNAUTHORIZED, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["code"] == LOGIN_CODE
    assert problem["title"] == LOGIN_TITLE
    assert problem["detail"] == LOGIN_DETAIL


async def test_the_site_help_turn_answers_from_the_real_sites_service(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """The scripted arc calls the catalog tool, which returns the live registry."""
    del patch_app_db_engine
    owner = await make_user(db_session)

    chunks = await _turn(
        app,
        owner.id,
        in_memory_jobs,
        conversation_id=uuid4(),
        prompt=_SITES_PROMPT,
        assistant_id=_SITE_HELP,
    )

    called = [c for c in chunks if c["type"] == "tool-input-available"]
    assert [c["toolName"] for c in called] == ["list_veupathdb_sites"]
    outputs = [c for c in chunks if c["type"] == "tool-output-available"]
    site_ids = {site["site_id"] for site in outputs[0]["output"]}
    assert {"plasmodb", "toxodb", "vectorbase"} <= site_ids
    assert _text(chunks) == SITES_REPLY


async def test_the_turn_leaves_an_assistant_message_with_its_usage(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
    in_memory_jobs: InMemoryConnector,
) -> None:
    """The runtime's finalize step runs for an assistant that declares no epilogue."""
    del patch_app_db_engine
    owner = await make_user(db_session)
    conversation_id = uuid4()

    await _turn(
        app,
        owner.id,
        in_memory_jobs,
        conversation_id=conversation_id,
        prompt=_SITES_PROMPT,
        assistant_id=_SITE_HELP,
    )

    async with session_maker() as session:
        rows = list(
            await session.scalars(
                select(Message).where(Message.conversation_id == conversation_id),
            ),
        )
    assistant_rows = [row for row in rows if row.role == "assistant"]
    assert len(assistant_rows) == 1
    usage = assistant_rows[0].metadata_["usage"]
    assert usage["totalTokens"] > 0


def test_the_two_assistants_resolve_different_graphs() -> None:
    """One registry, two architectures: the runtime cannot tell them apart."""
    registry = get_assistant_registry()

    pathfinder_nodes = set(
        registry.resolve("pathfinder").build_graph(InMemorySaver()).get_graph().nodes,
    )
    site_help_nodes = set(
        registry.resolve(_SITE_HELP).build_graph(InMemorySaver()).get_graph().nodes,
    )

    assert "lead" in pathfinder_nodes
    assert "lead" not in site_help_nodes
    assert "agent" in site_help_nodes
    assert "agent" not in pathfinder_nodes


async def test_a_signed_out_caller_can_begin_a_site_help_conversation(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """The creation path takes the same assistant id the chat body does."""
    del patch_app_db_engine
    owner = await make_user(db_session)
    conversation_id = uuid4()

    async with client_for(app, owner.id) as client:
        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/begin",
            json={"siteId": "plasmodb", "assistantId": _SITE_HELP},
        )

    assert response.status_code == 200, response.text
    assert response.json()["isNew"] is True
    assert await _assistant_of(session_maker, conversation_id) == _SITE_HELP


async def test_begin_refuses_an_assistant_the_thread_was_not_created_under(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    del patch_app_db_engine
    owner = await make_user(db_session)
    conversation = Conversation(
        user_id=owner.id,
        assistant_id="pathfinder",
        site_id="plasmodb",
        name="kinases",
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.commit()

    async with client_for(app, owner.id) as client:
        response = await client.post(
            f"/api/v1/conversations/{conversation.id}/begin",
            json={"siteId": "plasmodb", "assistantId": _SITE_HELP},
        )

    assert response.status_code == 409, response.text
    assert await _assistant_of(session_maker, conversation.id) == "pathfinder"


async def test_begin_without_an_assistant_still_takes_the_default(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    del patch_app_db_engine
    owner = await make_user(db_session)
    conversation_id = uuid4()

    async with client_for(app, owner.id) as client:
        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/begin",
            json={"siteId": "plasmodb"},
        )

    assert response.status_code == 200, response.text
    assert await _assistant_of(session_maker, conversation_id) == "pathfinder"
