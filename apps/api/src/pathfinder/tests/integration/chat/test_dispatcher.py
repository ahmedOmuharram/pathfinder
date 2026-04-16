"""Integration tests for the supervisor-driven LangGraph pipeline dispatcher."""

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
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.chat.dispatcher as dispatcher_module
import pathfinder.ai.graph.agents as agents_module
import pathfinder.ai.graph.nodes as nodes_module
import pathfinder.persistence.session as session_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.persistence.models import Chat
from pathfinder.persistence.repositories import MessagesRepository


def _parse_sse_frames(raw: bytes) -> list[tuple[str | None, str]]:
    """Split an SSE byte body into ``(event_name, data_payload)`` pairs.

    Any frame missing both ``event:`` and ``data:`` is skipped. ``event_name``
    is ``None`` when the frame omits the optional ``event:`` line.
    """
    text = raw.decode("utf-8", errors="ignore")
    out: list[tuple[str | None, str]] = []
    for frame in text.split("\n\n"):
        if not frame.strip():
            continue
        event_name: str | None = None
        data_lines: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
        if data_lines:
            out.append((event_name, "\n".join(data_lines)))
    return out


@pytest.fixture
def in_memory_compiled_graph(app: FastAPI) -> None:
    app.state.compiled_graph = build_graph(checkpointer=InMemorySaver())
    app.state.memory_store = None


def _make_phase_agent(name: str, text: str) -> Agent[AgentDeps, str]:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content=text)])

    async def _stream_fn(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield text

    model = FunctionModel(
        _fn,
        stream_function=_stream_fn,
        model_name=f"mock/deterministic:{name}",
    )
    return Agent(
        model,
        output_type=str,
        deps_type=AgentDeps,
        instructions="Return the prose.",
        name=f"mock-{name}",
    )


_STUB_TITLE = "Stub Conversation Title"


async def _stub_generate_title(
    first_user_message: str, provider: Any = None,
) -> str:
    del first_user_message, provider
    return _STUB_TITLE


_SUPERVISOR_PATH: list[str] = [
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
    "end",
]


def _supervisor_sequence() -> list[SupervisorDecision]:
    reasons = {
        "scoping": "framed",
        "discovery": "searches found",
        "planning": "plan submitted",
        "execution": "steps applied",
        "verification": "checks passed",
        "end": "turn complete",
    }
    return [
        SupervisorDecision(to=step, reason=reasons[step])
        for step in _SUPERVISOR_PATH
    ]


def _build_supervisor_stub_agent(seq: list[SupervisorDecision]) -> Agent[None, SupervisorDecision]:
    cursor = {"i": 0}

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        idx = cursor["i"]
        decision = seq[min(idx, len(seq) - 1)]
        cursor["i"] = idx + 1
        return ModelResponse(parts=[
            ToolCallPart(
                tool_name="final_result",
                args=json.dumps({"to": decision.to, "reason": decision.reason}),
                tool_call_id=f"sup_{idx}",
            )
        ])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        idx = cursor["i"]
        decision = seq[min(idx, len(seq) - 1)]
        cursor["i"] = idx + 1
        yield {
            0: DeltaToolCall(
                name="final_result",
                json_args=json.dumps({
                    "to": decision.to, "reason": decision.reason,
                }),
                tool_call_id=f"sup_{idx}",
            )
        }

    model = FunctionModel(
        _fn, stream_function=_stream, model_name="mock/supervisor",
    )
    return Agent(
        model,
        output_type=SupervisorDecision,
        instructions="Return the supervisor decision.",
        name="mock-supervisor",
        defer_model_check=True,
    )


@pytest.fixture
def stub_phase_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Agent[AgentDeps, str]]:
    stubs = {
        "scoping": _make_phase_agent("scoping", "scoping text"),
        "discovery": _make_phase_agent("discovery", "discovery text"),
        "planning": _make_phase_agent("planning", "planning text"),
        "execution": _make_phase_agent("execution", "execution text"),
        "verification": _make_phase_agent("verification", "verification text"),
    }
    monkeypatch.setattr(agents_module, "PHASE_AGENTS", stubs)
    monkeypatch.setattr(nodes_module, "PHASE_AGENTS", stubs)
    sup_agent = _build_supervisor_stub_agent(_supervisor_sequence())
    monkeypatch.setattr(
        nodes_module, "build_supervisor_agent", lambda provider=None: sup_agent,
    )
    monkeypatch.setattr(
        dispatcher_module, "generate_conversation_title", _stub_generate_title,
    )
    return stubs


def _submit_body(
    chat_id: str,
    text: str,
    *,
    parent_checkpoint_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "chatId": chat_id,
        "userId": user_id or str(uuid4()),
        "message": text,
        "siteId": "plasmodb",
        "mode": "strategy",
    }
    if parent_checkpoint_id is not None:
        body["parentCheckpointId"] = parent_checkpoint_id
    return body


@pytest.mark.asyncio
async def test_chat_returns_sse_happy_path(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
    in_memory_compiled_graph: None,
) -> None:
    del stub_phase_agents, in_memory_compiled_graph
    chat_id = str(uuid4())

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
        assert "x-vercel-ai-ui-message-stream" not in resp.headers
        raw = await resp.aread()

    frames = _parse_sse_frames(raw)
    assert frames, "expected at least one SSE frame"
    chunks = [json.loads(payload) for _name, payload in frames]

    phase_starts = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-phase-start"
    ]
    phase_finishes = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-phase-finish"
    ]
    assert phase_starts, chunks
    assert phase_finishes, chunks
    assert len(phase_starts) == len(phase_finishes), (phase_starts, phase_finishes)

    phases_started = [c["data"]["phase"] for c in phase_starts]
    assert "scoping" in phases_started, phases_started
    assert "verification" in phases_started, phases_started

    phase_change_events = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-phase-change"
    ]
    assert phase_change_events, "expected at least one phase-change event"

    title_events = [
        c
        for c in chunks
        if c.get("type") == "custom"
        and c.get("kind") == "data-conversation-title"
    ]
    assert title_events, "expected at least one conversation-title event"
    assert title_events[-1]["data"]["title"] == _STUB_TITLE

    async with session_module.async_session_factory() as session:
        chat_row = await session.get(Chat, UUID(chat_id))
    assert chat_row is not None
    assert chat_row.user_id is not None
    assert chat_row.site_id == "plasmodb", chat_row.site_id
    assert chat_row.name == _STUB_TITLE, chat_row.name


@pytest.mark.asyncio
async def test_chat_persists_user_and_assistant_messages(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
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
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
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
    assert final.metadata_.get("turnCompleted") is True


@pytest.mark.asyncio
async def test_dispatcher_sse_frame_format(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
    in_memory_compiled_graph: None,
) -> None:
    """Every emitted frame MUST carry ``event: stream`` before its ``data:`` line."""
    del stub_phase_agents, in_memory_compiled_graph
    chat_id = str(uuid4())

    async with authed_client.stream(
        "POST", "/api/v1/chat", json=_submit_body(chat_id, "frame format check"),
    ) as resp:
        assert resp.status_code == 200
        raw = await resp.aread()

    frames = _parse_sse_frames(raw)
    assert frames, "expected at least one SSE frame"
    for event_name, payload in frames:
        assert event_name == "stream", (
            f"frame missing 'event: stream' header; "
            f"got event_name={event_name!r}, payload={payload!r}"
        )
        # data payload must always be valid JSON — never a [DONE] sentinel.
        parsed = json.loads(payload)
        assert "type" in parsed, f"frame missing 'type': {parsed!r}"


@pytest.mark.asyncio
async def test_dispatcher_emits_terminal_done_event(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
    in_memory_compiled_graph: None,
) -> None:
    """Final SSE frame MUST be a typed ``DoneEvent(reason="completed")``."""
    del stub_phase_agents, in_memory_compiled_graph
    chat_id = str(uuid4())

    async with authed_client.stream(
        "POST", "/api/v1/chat", json=_submit_body(chat_id, "done event check"),
    ) as resp:
        assert resp.status_code == 200
        raw = await resp.aread()

    frames = _parse_sse_frames(raw)
    assert frames
    last_event_name, last_payload = frames[-1]
    assert last_event_name == "stream"
    last = json.loads(last_payload)
    assert last["type"] == "done", last
    assert last["reason"] == "completed", last


@pytest.mark.asyncio
async def test_dispatcher_emits_checkpoint_events(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
    db_cleaner: None,
    patch_app_db_engine: None,
    app: FastAPI,
) -> None:
    """``stream_mode='debug'`` must surface a ``CheckpointEvent`` per node boundary."""
    del stub_phase_agents, db_cleaner, patch_app_db_engine
    # Use the durable AsyncPostgresSaver so checkpoint emission has a
    # parent_id chain — InMemorySaver doesn't expose parent_checkpoint_id
    # in the debug payload reliably.
    from pathfinder.ai.chat.checkpointer import lifespan_checkpointer  # noqa: PLC0415
    from pathfinder.platform.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    async with lifespan_checkpointer(settings.database_url) as saver:
        app.state.compiled_graph = build_graph(checkpointer=saver)
        app.state.memory_store = None

        chat_id = str(uuid4())
        async with authed_client.stream(
            "POST",
            "/api/v1/chat",
            json=_submit_body(chat_id, "drive the pipeline"),
        ) as resp:
            assert resp.status_code == 200
            raw = await resp.aread()

    frames = _parse_sse_frames(raw)
    chunks = [json.loads(payload) for _name, payload in frames]
    checkpoints = [c for c in chunks if c.get("type") == "checkpoint"]
    assert len(checkpoints) >= 1, (
        f"expected at least one CheckpointEvent, got {len(checkpoints)}"
    )
    first = checkpoints[0]
    assert "checkpointId" in first, first
    assert "step" in first, first
    assert "createdAt" in first, first


@pytest.mark.asyncio
async def test_dispatcher_accepts_parent_checkpoint_id(
    authed_client: httpx.AsyncClient,
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
    db_cleaner: None,
    patch_app_db_engine: None,
    app: FastAPI,
) -> None:
    """``parentCheckpointId`` in the request body must thread to the new turn's checkpoint."""
    del stub_phase_agents, db_cleaner, patch_app_db_engine
    from sqlalchemy import text  # noqa: PLC0415

    from pathfinder.ai.chat.checkpointer import lifespan_checkpointer  # noqa: PLC0415
    from pathfinder.platform.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    async with lifespan_checkpointer(settings.database_url) as saver:
        app.state.compiled_graph = build_graph(checkpointer=saver)
        app.state.memory_store = None

        chat_id = str(uuid4())

        async with authed_client.stream(
            "POST", "/api/v1/chat", json=_submit_body(chat_id, "first turn"),
        ) as resp:
            assert resp.status_code == 200
            await resp.aread()

        async with session_module.async_session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT checkpoint_id, parent_checkpoint_id "
                        "FROM checkpoints WHERE thread_id = :tid "
                        "ORDER BY (metadata->>'step')::int ASC NULLS LAST"
                    ),
                    {"tid": chat_id},
                )
            ).fetchall()
        assert rows, "first turn must produce checkpoints"
        midpoint_idx = max(0, len(rows) // 2)
        chosen = rows[midpoint_idx]
        target_parent = chosen.checkpoint_id

        async with authed_client.stream(
            "POST",
            "/api/v1/chat",
            json=_submit_body(
                chat_id,
                "branched second turn",
                parent_checkpoint_id=target_parent,
            ),
        ) as resp2:
            assert resp2.status_code == 200
            await resp2.aread()

        async with session_module.async_session_factory() as session:
            new_rows = (
                await session.execute(
                    text(
                        "SELECT checkpoint_id, parent_checkpoint_id, "
                        "(metadata->>'step')::int AS step "
                        "FROM checkpoints WHERE thread_id = :tid "
                        "ORDER BY (metadata->>'step')::int ASC NULLS LAST"
                    ),
                    {"tid": chat_id},
                )
            ).fetchall()

    descendants = [r for r in new_rows if r.parent_checkpoint_id == target_parent]
    assert descendants, (
        f"expected a checkpoint whose parent is {target_parent!r}, "
        f"got {[(r.checkpoint_id, r.parent_checkpoint_id) for r in new_rows]}"
    )
