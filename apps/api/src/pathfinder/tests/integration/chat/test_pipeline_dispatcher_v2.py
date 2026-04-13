"""Integration tests for the new pipeline dispatcher — wired to ``/api/v2/chat``.

The dispatcher drives the 5-phase state machine by running each phase agent
via ``VercelAIAdapter`` and reading ``run.result.output`` (the typed
``PhaseDecision``) to transition the state machine.

These tests use a stubbed phase agent set (each backed by a ``FunctionModel``
that produces a deterministic ``PhaseDecision``) so the entire pipeline can
execute without real LLM calls. The mock chat-provider used by the rest of
the integration suite predates ``output_type=<PhaseDecision>`` and cannot
produce structured outputs, so we override ``PHASE_AGENTS`` locally.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.agents as agents_module
import pathfinder.persistence.session as session_module
import pathfinder.services.chat.pipeline_dispatcher as dispatcher_module
from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import MessagesRepository


def _deferred_tool_call(
    decision_name: str, payload: dict[str, Any]
) -> ToolCallPart:
    """Build a structured-output tool call for a ``PhaseDecision`` model.

    pydantic-ai wraps ``output_type=SomeModel`` as a deferred tool named
    ``final_result`` — the model "calls" it with the structured payload as
    args, and pydantic-ai validates + exits.
    """
    return ToolCallPart(
        tool_name="final_result",
        args=json.dumps(payload),
        tool_call_id=f"mock_{decision_name}",
    )


def _make_phase_agent(
    name: str,
    decision_payload: dict[str, Any],
    followup_text: str,
) -> Agent[AgentDeps, Any]:
    """Build a minimal pydantic-ai agent that emits a single ``PhaseDecision``.

    Uses ``FunctionModel`` so it runs deterministically with zero LLM calls.
    The agent has no tools beyond the implicit ``final_result`` deferred tool
    injected by ``output_type=``.
    """

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


_SCOPING_PAYLOAD = {
    "next_action": "advance_to_discovery",
    "problem_frame": "mock problem frame",
    "discovered_searches": ["GenesByTaxon"],
    "reason": "mock scoping done",
}
_DISCOVERY_PAYLOAD = {
    "next_action": "advance_to_planning",
    "discovered_searches": ["GenesByTaxon"],
    "problem_frame_refined": None,
    "reason": "mock discovery done",
}
_PLANNING_PAYLOAD = {
    "next_action": "advance_to_execution",
    "plan_id": "plan_mock",
    "reason": "mock planning done",
}
_EXECUTION_PAYLOAD = {
    "next_action": "advance_to_verification",
    "executed_steps": ["step_1"],
    "reason": "mock execution done",
}
_VERIFICATION_PAYLOAD = {
    "next_action": "complete",
    "verification_notes": "mock verification ok",
    "reason": "mock verification done",
}


@pytest.fixture
def stub_phase_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Agent[AgentDeps, Any]]:
    """Replace ``PHASE_AGENTS`` with deterministic ``FunctionModel``-backed agents."""
    stubs = {
        "scoping": _make_phase_agent("scoping", _SCOPING_PAYLOAD, "scoping text"),
        "discovery": _make_phase_agent("discovery", _DISCOVERY_PAYLOAD, "discovery text"),
        "planning": _make_phase_agent("planning", _PLANNING_PAYLOAD, "planning text"),
        "execution": _make_phase_agent("execution", _EXECUTION_PAYLOAD, "execution text"),
        "verification": _make_phase_agent(
            "verification", _VERIFICATION_PAYLOAD, "verification text"
        ),
    }
    monkeypatch.setattr(agents_module, "PHASE_AGENTS", stubs)
    # Also patch the symbol imported into the dispatcher module.
    monkeypatch.setattr(dispatcher_module, "PHASE_AGENTS", stubs)
    return stubs


def _submit_body(chat_id: str, text: str) -> dict[str, Any]:
    """Shape the client-side ``prepareSendMessagesRequest`` body.

    Matches the frontend transport config — one ``message`` (the latest),
    plus client metadata in ``metadata``.
    """
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
async def test_v2_chat_returns_sse_happy_path(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
) -> None:
    """POST /api/v2/chat returns a valid AI SDK UI Message Stream."""
    del stub_phase_agents
    chat_id = str(uuid4())

    async with session_module.async_session_factory() as session:
        session.add(Chat(id=UUID(chat_id)))
        await session.commit()

    chunks: list[dict[str, Any]] = []
    async with authed_client.stream(
        "POST",
        "/api/v2/chat",
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
    # Exactly one lifecycle pair per turn (filter duplicates emitted per phase).
    assert chunk_types.count("start") == 1, chunk_types
    assert chunk_types.count("finish") == 1, chunk_types
    # Per-phase MessageMetadataChunk tagged with the phase name.
    metadata_chunks = [c for c in chunks if c.get("type") == "message-metadata"]
    phases_seen = [
        (chunk.get("messageMetadata") or {}).get("phase") for chunk in metadata_chunks
    ]
    assert "scoping" in phases_seen, phases_seen
    # Structured output tool calls surface as tool-input-available chunks.
    tool_types = [c.get("type") for c in chunks if c.get("type", "").startswith("tool-")]
    assert tool_types, "expected tool-* chunks from final_result deferred tool"


@pytest.mark.asyncio
async def test_v2_chat_persists_user_and_assistant_messages(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
) -> None:
    """After a successful turn, both user and assistant rows land in ``messages``."""
    del stub_phase_agents
    chat_id = str(uuid4())

    async with session_module.async_session_factory() as session:
        session.add(Chat(id=UUID(chat_id)))
        await session.commit()

    async with authed_client.stream(
        "POST", "/api/v2/chat", json=_submit_body(chat_id, "hi")
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
async def test_v2_chat_advances_state_machine_through_all_phases(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
) -> None:
    """All 5 phases run in order; the assistant message carries phase metadata."""
    del stub_phase_agents
    chat_id = str(uuid4())

    async with session_module.async_session_factory() as session:
        session.add(Chat(id=UUID(chat_id)))
        await session.commit()

    async with authed_client.stream(
        "POST", "/api/v2/chat", json=_submit_body(chat_id, "drive the pipeline")
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
    # Last phase to run before terminal 'completed' state is 'verification'.
    assert final.metadata_.get("phase") == "verification", final.metadata_
