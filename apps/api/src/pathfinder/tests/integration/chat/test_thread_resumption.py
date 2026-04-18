"""Verify checkpointed graph state survives across discrete graph invocations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.graph.agents as agents_module
import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.persistence.models import Conversation, User
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _phase_agent(phase: str, text: str) -> Agent[AgentDeps, str]:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content=text)])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield text

    return Agent(
        FunctionModel(_fn, stream_function=_stream, model_name=f"mock:{phase}"),
        output_type=str,
        deps_type=AgentDeps,
        instructions="return prose",
        name=f"mock-{phase}",
    )


def _supervisor_stub(decisions: list[SupervisorDecision]) -> Agent[None, SupervisorDecision]:
    cursor = {"i": 0}

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        idx = cursor["i"]
        d = decisions[min(idx, len(decisions) - 1)]
        cursor["i"] = idx + 1
        return ModelResponse(parts=[
            ToolCallPart(
                tool_name="final_result",
                args=json.dumps({"to": d.to, "reason": d.reason}),
                tool_call_id=f"sup_{idx}",
            )
        ])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        idx = cursor["i"]
        d = decisions[min(idx, len(decisions) - 1)]
        cursor["i"] = idx + 1
        yield {
            0: DeltaToolCall(
                name="final_result",
                json_args=json.dumps({"to": d.to, "reason": d.reason}),
                tool_call_id=f"sup_{idx}",
            )
        }

    return Agent(
        FunctionModel(_fn, stream_function=_stream, model_name="mock/supervisor"),
        output_type=SupervisorDecision,
        instructions="return decision",
        name="mock-supervisor",
        defer_model_check=True,
    )


_FULL_PATH = ["scoping", "discovery", "planning", "execution", "verification", "end"]


def _full_supervisor_decisions() -> list[SupervisorDecision]:
    return [
        SupervisorDecision(to=t, reason=f"-> {t}") for t in _FULL_PATH
    ]


@pytest.fixture
def stub_phase_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Agent[AgentDeps, str]]:
    stubs = {
        "scoping": _phase_agent("scoping", "scoping"),
        "discovery": _phase_agent("discovery", "discovery"),
        "planning": _phase_agent("planning", "planning"),
        "execution": _phase_agent("execution", "execution"),
        "verification": _phase_agent("verification", "verification"),
    }
    monkeypatch.setattr(agents_module, "PHASE_AGENTS", stubs)
    monkeypatch.setattr(nodes_module, "PHASE_AGENTS", stubs)
    # Two consecutive turns each need the full sequence; concatenate.
    decisions = _full_supervisor_decisions() + _full_supervisor_decisions()
    sup = _supervisor_stub(decisions)
    monkeypatch.setattr(
        nodes_module, "build_supervisor_agent", lambda provider=None: sup,
    )
    return stubs


@pytest.mark.asyncio
async def test_second_turn_inherits_state_from_checkpoint(
    stub_phase_agents: dict[str, Agent[AgentDeps, str]],
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del stub_phase_agents, db_cleaner, patch_app_db_engine
    saver = InMemorySaver()
    graph = build_graph(checkpointer=saver)
    conversation_id = uuid4()
    user_id = uuid4()
    config = {"configurable": {"thread_id": str(conversation_id)}}

    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(Conversation(id=conversation_id, user_id=user_id, site_id="plasmodb", name=""))
        await session.commit()

    settings = get_settings()
    async with lifespan_memory_store(settings.database_url) as memory_store:
        context = Context(
            site_id="plasmodb",
            user_id=user_id,
            strategy_session=StrategySession(site_id="plasmodb"),
            db_session_factory=async_session_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
            memory_store=memory_store,
        )

        initial_state = PipelineState(
            conversation_id=conversation_id,
            user_id=user_id,
            site_id="plasmodb",
            mode="strategy",
            user_message_id=uuid4(),
            user_prompt="turn one",
            user_parts=[{"type": "text", "text": "turn one"}],
            turn_trace_id=str(uuid4()),
            turn_created_at="2026-04-14T00:00:00+00:00",
        )

        async for _ in graph.astream(
            initial_state.model_dump(),
            config=config,
            context=context,
            stream_mode=["custom"],
        ):
            pass

        snap_after_turn1 = await graph.aget_state(config)
        history_len_after_turn1 = len(snap_after_turn1.values["message_history"])
        assert history_len_after_turn1 > 0
        assert snap_after_turn1.values["current_phase"] == "verification"

        second_turn: dict[str, Any] = {
            "user_message_id": uuid4(),
            "user_prompt": "turn two",
            "user_parts": [{"type": "text", "text": "turn two"}],
            "turn_trace_id": str(uuid4()),
            "turn_created_at": "2026-04-14T00:01:00+00:00",
            "supervisor_call_count": 0,
            "phase_call_counts": {},
            "current_phase": None,
            "last_routing_reason": None,
            "last_assistant_prose": "",
        }
        async for _ in graph.astream(
            second_turn,
            config=config,
            context=context,
            stream_mode=["custom"],
        ):
            pass

        snap_after_turn2 = await graph.aget_state(config)
        history_len_after_turn2 = len(snap_after_turn2.values["message_history"])

        assert history_len_after_turn2 > history_len_after_turn1, (
            "second turn should append to checkpointed history, not replace it"
        )
        assert snap_after_turn2.values["current_phase"] == "verification"
