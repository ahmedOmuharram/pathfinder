"""Integration tests for the new LangGraph-backed pipeline dispatcher."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.chat.dispatcher as dispatcher_module
import pathfinder.ai.graph.agents as agents_module
import pathfinder.ai.graph.nodes as nodes_module
import pathfinder.persistence.session as session_module
from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import MessagesRepository


@pytest.fixture
def in_memory_compiled_graph(app: FastAPI) -> None:
    app.state.compiled_graph = build_graph(checkpointer=InMemorySaver())
    # Dispatcher reads app.state.memory_store; tests that don't exercise retrieval
    # can pass None (nodes short-circuit on a missing store).
    app.state.memory_store = None


def _deferred_tool_call(name: str, payload: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name="final_result",
        args=json.dumps(payload),
        tool_call_id=f"mock_{name}",
    )


def _make_phase_agent(
    name: str,
    decision_payload: dict[str, Any],
    followup_text: str,
) -> Agent[AgentDeps, Any]:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[_deferred_tool_call(name, decision_payload)])

    async def _stream_fn(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        call = _deferred_tool_call(name, decision_payload)
        yield {
            0: DeltaToolCall(
                name=call.tool_name,
                json_args=call.args_as_json_str(),
                tool_call_id=call.tool_call_id,
            )
        }
        yield followup_text

    model = FunctionModel(
        _fn,
        stream_function=_stream_fn,
        model_name=f"mock/deterministic:{name}",
    )

    decision_type: type[Any]
    match name:
        case "scoping":
            decision_type = ScopingDecision
        case "discovery":
            decision_type = DiscoveryDecision
        case "planning":
            decision_type = PlanningDecision
        case "execution":
            decision_type = ExecutionDecision
        case "verification":
            decision_type = VerificationDecision
        case _:
            msg = f"unknown phase {name}"
            raise AssertionError(msg)

    return Agent(
        model,
        output_type=decision_type,
        deps_type=AgentDeps,
        instructions="Return the final decision.",
        name=f"mock-{name}",
    )


_SCOPING_PAYLOAD = {"next_action": "advance_to_discovery"}
_DISCOVERY_PAYLOAD = {"next_action": "advance_to_planning"}
_PLANNING_PAYLOAD = {"next_action": "advance_to_execution"}
_EXECUTION_PAYLOAD = {"next_action": "advance_to_verification"}
_VERIFICATION_PAYLOAD = {"next_action": "complete"}

_STUB_TITLE = "Stub Conversation Title"


async def _stub_generate_title(
    first_user_message: str, provider: Any = None,
) -> str:
    del first_user_message, provider
    return _STUB_TITLE


@pytest.fixture
def stub_phase_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Agent[AgentDeps, Any]]:
    stubs = {
        "scoping": _make_phase_agent(
            "scoping", _SCOPING_PAYLOAD, "scoping text"
        ),
        "discovery": _make_phase_agent(
            "discovery", _DISCOVERY_PAYLOAD, "discovery text"
        ),
        "planning": _make_phase_agent(
            "planning", _PLANNING_PAYLOAD, "planning text"
        ),
        "execution": _make_phase_agent(
            "execution", _EXECUTION_PAYLOAD, "execution text"
        ),
        "verification": _make_phase_agent(
            "verification", _VERIFICATION_PAYLOAD, "verification text"
        ),
    }
    monkeypatch.setattr(agents_module, "PHASE_AGENTS", stubs)
    monkeypatch.setattr(nodes_module, "PHASE_AGENTS", stubs)
    monkeypatch.setattr(
        dispatcher_module, "generate_conversation_title", _stub_generate_title,
    )
    return stubs


def _submit_body(chat_id: str, text: str) -> dict[str, Any]:
    return {
        "id": chat_id,
        "message": {
            "id": str(uuid4()),
            "role": "user",
            "parts": [{"type": "text", "text": text}],
        },
        "metadata": {
            "mode": "strategy",
            "siteId": "plasmodb",
            "pipeline": None,
        },
    }


@pytest.mark.asyncio
async def test_chat_returns_sse_happy_path(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
    in_memory_compiled_graph: None,
) -> None:
    del stub_phase_agents, in_memory_compiled_graph
    chat_id = str(uuid4())

    chunks: list[dict[str, Any]] = []
    async with authed_client.stream(
        "POST",
        "/api/v1/chat",
        json=_submit_body(chat_id, "find drug targets for PfATP4"),
    ) as resp:
        assert resp.status_code == 200, (
            f"expected 200, got {resp.status_code}: "
            f"{(await resp.aread()).decode('utf-8', errors='ignore')}"
        )
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers.get("x-vercel-ai-ui-message-stream") == "v1"

        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            if payload == "[DONE]":
                break
            chunks.append(json.loads(payload))

    chunk_types = [c.get("type") for c in chunks]
    assert "start" in chunk_types, chunk_types
    assert "finish" in chunk_types, chunk_types
    assert chunk_types.count("start") == chunk_types.count("finish"), chunk_types

    start_chunks = [c for c in chunks if c.get("type") == "start"]
    phases_seen = [
        (chunk.get("messageMetadata") or {}).get("phase") for chunk in start_chunks
    ]
    assert "scoping" in phases_seen, phases_seen
    assert "verification" in phases_seen, phases_seen

    metadata_chunks = [c for c in chunks if c.get("type") == "message-metadata"]
    title_metadata = [
        c
        for c in metadata_chunks
        if (c.get("messageMetadata") or {}).get("conversationTitle")
    ]
    assert title_metadata, "expected at least one conversationTitle metadata chunk"
    assert (
        title_metadata[-1]["messageMetadata"]["conversationTitle"] == _STUB_TITLE
    )

    async with session_module.async_session_factory() as session:
        chat_row = await session.get(Chat, UUID(chat_id))
    assert chat_row is not None, "lazy chat creation should insert chats row"
    assert chat_row.user_id is not None, "user_id must be populated"
    assert chat_row.site_id == "plasmodb", chat_row.site_id
    assert chat_row.name == _STUB_TITLE, chat_row.name


@pytest.mark.asyncio
async def test_chat_persists_user_and_assistant_messages(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
    in_memory_compiled_graph: None,
) -> None:
    del stub_phase_agents, in_memory_compiled_graph
    chat_id = str(uuid4())

    async with authed_client.stream(
        "POST", "/api/v1/chat", json=_submit_body(chat_id, "hi")
    ) as resp:
        assert resp.status_code == 200
        async for _line in resp.aiter_lines():
            pass

    async with session_module.async_session_factory() as session:
        repo = MessagesRepository(session)
        rows = await repo.list_messages_for_chat(UUID(chat_id))

    roles = [r.role for r in rows]
    assert "user" in roles, f"expected user row, got roles={roles}"
    assert "assistant" in roles, f"expected assistant row, got roles={roles}"


@pytest.mark.asyncio
async def test_chat_advances_through_all_phases(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
    in_memory_compiled_graph: None,
) -> None:
    del stub_phase_agents, in_memory_compiled_graph
    chat_id = str(uuid4())

    async with authed_client.stream(
        "POST", "/api/v1/chat", json=_submit_body(chat_id, "drive the pipeline")
    ) as resp:
        assert resp.status_code == 200
        async for _line in resp.aiter_lines():
            pass

    async with session_module.async_session_factory() as session:
        repo = MessagesRepository(session)
        rows = await repo.list_messages_for_chat(UUID(chat_id))

    assistant_rows = [r for r in rows if r.role == "assistant"]
    assert len(assistant_rows) >= 1
    final = assistant_rows[-1]
    assert final.metadata_.get("phase") == "verification", final.metadata_
