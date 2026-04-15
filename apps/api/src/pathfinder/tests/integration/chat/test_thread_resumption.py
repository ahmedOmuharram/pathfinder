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
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.graph.agents as agents_module
import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.persistence.models import Chat, User
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _decision_call(name: str, payload: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name="final_result",
        args=json.dumps(payload),
        tool_call_id=f"mock_{name}_{uuid4().hex[:6]}",
    )


def _phase_agent(
    phase: str, payload: dict[str, Any], text: str
) -> Agent[AgentDeps, Any]:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[_decision_call(phase, payload)])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        call = _decision_call(phase, payload)
        yield {
            0: DeltaToolCall(
                name=call.tool_name,
                json_args=call.args_as_json_str(),
                tool_call_id=call.tool_call_id,
            )
        }
        yield text

    decision_type: type[Any]
    match phase:
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
            msg = f"unknown phase {phase}"
            raise AssertionError(msg)

    return Agent(
        FunctionModel(_fn, stream_function=_stream, model_name=f"mock:{phase}"),
        output_type=decision_type,
        deps_type=AgentDeps,
        instructions="return the decision",
        name=f"mock-{phase}",
    )


@pytest.fixture
def stub_phase_agents(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Agent[AgentDeps, Any]]:
    stubs = {
        "scoping": _phase_agent(
            "scoping", {"next_action": "advance_to_discovery"}, "scoping"
        ),
        "discovery": _phase_agent(
            "discovery", {"next_action": "advance_to_planning"}, "discovery"
        ),
        "planning": _phase_agent(
            "planning", {"next_action": "advance_to_execution"}, "planning"
        ),
        "execution": _phase_agent(
            "execution", {"next_action": "advance_to_verification"}, "execution"
        ),
        "verification": _phase_agent(
            "verification", {"next_action": "complete"}, "verification"
        ),
    }
    monkeypatch.setattr(agents_module, "PHASE_AGENTS", stubs)
    monkeypatch.setattr(nodes_module, "PHASE_AGENTS", stubs)
    return stubs


@pytest.mark.asyncio
async def test_second_turn_inherits_state_from_checkpoint(
    stub_phase_agents: dict[str, Agent[AgentDeps, Any]],
    db_cleaner: None,
    patch_app_db_engine: None,
) -> None:
    del stub_phase_agents, db_cleaner, patch_app_db_engine
    saver = InMemorySaver()
    graph = build_graph(checkpointer=saver)
    chat_id = uuid4()
    user_id = uuid4()
    config = {"configurable": {"thread_id": str(chat_id)}}

    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        session.add(Chat(id=chat_id, user_id=user_id, site_id="plasmodb", name=""))
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
            chat_id=chat_id,
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
        assert "verification" in snap_after_turn1.values["phase_decisions"]

        second_turn = {
            "user_message_id": uuid4(),
            "user_prompt": "turn two",
            "user_parts": [{"type": "text", "text": "turn two"}],
            "turn_trace_id": str(uuid4()),
            "turn_created_at": "2026-04-14T00:01:00+00:00",
            "phase_decisions": {},
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
        assert snap_after_turn2.values["phase_decisions"]["verification"]
