"""A dispatch stopped by a budget or by the repetition guard still records usage."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext, Tool
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead import sub_agent_stream
from pathfinder.ai.lead.sub_agent_dispatch import frame_work_order, run_frame
from pathfinder.ai.lead.sub_agent_tools import LeadDeps, SubAgentRunUsage
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.tests._support.sub_agents import pinned_sub_agent

_INSTRUCTIONS = "Call the ping tool."


def _endless_tool_call_model() -> FunctionModel:
    """A model that calls ``ping`` on every step and never finishes."""

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(
            parts=[ToolCallPart(tool_name="ping", args="{}", tool_call_id=uuid4().hex)]
        )

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[dict[int, DeltaToolCall]]:
        part = _fn(messages, info).parts[0]
        assert isinstance(part, ToolCallPart)
        yield {
            0: DeltaToolCall(
                name=part.tool_name,
                json_args=part.args_as_json_str(),
                tool_call_id=part.tool_call_id,
            ),
        }

    return FunctionModel(_fn, stream_function=_stream, model_name="scripted")


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _deps(usage_log: list[SubAgentRunUsage]) -> LeadDeps:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="Find kinases.",
    )
    context = Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=context,
        retrieved_memories=[],
        record_sub_agent_usage=usage_log.append,
    )


class _Collector:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


@pytest.fixture
def collector(monkeypatch: pytest.MonkeyPatch) -> _Collector:
    captured = _Collector()
    monkeypatch.setattr(sub_agent_stream, "get_stream_writer", lambda: captured)
    return captured


@pytest.fixture
def pinned_frame(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def ping(ctx: RunContext[AgentDeps]) -> str:
        del ctx
        return "pong"

    toolset = FunctionToolset[AgentDeps](tools=[Tool(ping)])
    with pinned_sub_agent(
        monkeypatch,
        "frame",
        model=_endless_tool_call_model(),
        toolsets=[toolset],
        instructions=_INSTRUCTIONS,
    ):
        yield


@pytest.mark.asyncio
async def test_budget_stopped_dispatch_records_its_usage(
    monkeypatch: pytest.MonkeyPatch,
    collector: _Collector,
    pinned_frame: None,
) -> None:
    monkeypatch.setattr(
        sub_agent_stream,
        "phase_usage_limits",
        lambda declared_criteria: UsageLimits(
            request_limit=3,
            tool_calls_limit=1,
            total_tokens_limit=2_000_000,
        ),
    )
    monkeypatch.setattr(
        sub_agent_stream,
        "phase_override_kwargs",
        lambda runtime, role: {},
    )
    usage_log: list[SubAgentRunUsage] = []
    deps = _deps(usage_log)

    await run_frame(
        deps=deps,
        parent_tool_call_id="call_frame_1",
        work_order=frame_work_order("operationalize the goal", ""),
    )

    assert usage_log, "a budget-stopped dispatch must record its usage"
    recorded = usage_log[-1]
    assert recorded.parent_tool_call_id == "call_frame_1"
    assert recorded.usage.total_tokens > 0
