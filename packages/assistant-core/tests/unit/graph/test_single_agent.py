"""The stock single-agent turn graph, driven by a scripted model.

One agent answers the turn. The helper owns the chunk emission, the token and
cost accounting, and the cancel check; it names no assistant.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from assistant_core.graph import turn_message
from assistant_core.graph.runtime import AssistantDeps, TurnContext
from assistant_core.graph.single_agent import single_agent_graph
from assistant_core.graph.turn_state import TurnState
from assistant_core.platform.db import async_session_factory
from assistant_core.spec import turn_input

type ProbeAgent = Agent[AssistantDeps, str]


class _Charges:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int, Decimal]] = []

    async def __call__(self, user_id: UUID, tokens: int, cost_usd: Decimal) -> None:
        self.calls.append((user_id, tokens, cost_usd))


def _deps(state: TurnState, context: TurnContext) -> AssistantDeps:
    return AssistantDeps(
        site_id=context.site_id,
        user_id=context.user_id,
        conversation_id=state.conversation_id,
        cancel_event=context.cancel_event,
    )


def _text_model(text: str) -> FunctionModel:
    def _respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[TextPart(content=text)])

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield text

    return FunctionModel(_respond, stream_function=_stream, model_name="test:text")


def _has_tool_call(messages: list[ModelMessage]) -> bool:
    return any(
        isinstance(part, ToolCallPart)
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
    )


def _tool_then_text_model(tool_name: str, text: str) -> FunctionModel:
    def _respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del info
        if _has_tool_call(messages):
            return ModelResponse(parts=[TextPart(content=text)])
        return ModelResponse(
            parts=[ToolCallPart(tool_name=tool_name, args={}, tool_call_id="call-1")],
        )

    async def _stream(
        messages: list[ModelMessage],
        info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del info
        if _has_tool_call(messages):
            yield text
            return
        yield {0: DeltaToolCall(name=tool_name, json_args="{}", tool_call_id="call-1")}

    return FunctionModel(_respond, stream_function=_stream, model_name="test:tool")


def _agent(model: FunctionModel, tools: list[Callable[[], Any]]) -> ProbeAgent:
    return Agent(
        model,
        output_type=str,
        deps_type=AssistantDeps,
        instructions="Answer.",
        tools=list(tools),
        name="probe",
    )


def _context(cancel: asyncio.Event) -> TurnContext:
    return TurnContext(
        site_id="plasmodb",
        user_id=uuid4(),
        db_session_factory=async_session_factory,
        cancel_event=cancel,
    )


async def _run(
    model: FunctionModel,
    *,
    tools: list[Callable[[], Any]] | None = None,
    cancel: asyncio.Event | None = None,
    charges: _Charges | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context = _context(cancel or asyncio.Event())
    graph = single_agent_graph(
        checkpointer=InMemorySaver(),
        state_type=TurnState,
        context_type=TurnContext,
        build_agent=lambda: _agent(model, tools or []),
        build_deps=_deps,
        charge_usage=charges or _Charges(),
    )
    conversation_id = uuid4()
    state = TurnState(
        conversation_id=conversation_id,
        user_id=context.user_id,
        site_id="plasmodb",
        mode="strategy",
        user_prompt="which sites",
    )
    config: dict[str, Any] = {"configurable": {"thread_id": str(conversation_id)}}
    chunks: list[dict[str, Any]] = []
    async for _mode, payload in graph.astream(
        turn_input(state),
        config=config,
        context=context,
        stream_mode=["custom"],
    ):
        chunks.append(payload["chunk"])
    snapshot = await graph.aget_state(config)
    return chunks, snapshot.values


@pytest.fixture(autouse=True)
def _no_durable_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """The turn-message write reads the durable log; this suite has no database."""

    async def _empty(
        conversation_id: UUID,
        after: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        del conversation_id
        return after, []

    monkeypatch.setattr(turn_message, "fetch_chunks_after", _empty)


def test_the_graph_is_the_agent_node_and_the_runtime_s_finalize() -> None:
    graph = single_agent_graph(
        checkpointer=InMemorySaver(),
        state_type=TurnState,
        context_type=TurnContext,
        build_agent=lambda: _agent(_text_model("hi"), []),
        build_deps=_deps,
        charge_usage=_Charges(),
    )

    assert set(graph.get_graph().nodes) >= {"agent", "finalize_turn"}


async def test_the_agent_s_answer_streams_as_text_chunks() -> None:
    chunks, _values = await _run(_text_model("PlasmoDB and ToxoDB."))

    assert [c["type"] for c in chunks] == [
        "data-turn-status",
        "start-step",
        "text-start",
        "text-delta",
        "text-end",
        "message-metadata",
        "finish-step",
        "data-turn-usage",
    ]
    assert chunks[3]["delta"] == "PlasmoDB and ToxoDB."


async def test_a_tool_call_streams_its_input_and_output() -> None:
    async def ping() -> str:
        """Answer with pong."""
        return "pong"

    chunks, _values = await _run(
        _tool_then_text_model("ping", "Done."),
        tools=[ping],
    )

    types = [c["type"] for c in chunks]
    assert "tool-input-available" in types
    assert "tool-output-available" in types
    output = next(c for c in chunks if c["type"] == "tool-output-available")
    assert output["output"] == "pong"
    assert types[-1] == "data-turn-usage"


async def test_the_turn_s_tokens_and_cost_land_on_the_state() -> None:
    charges = _Charges()

    chunks, values = await _run(_text_model("hello"), charges=charges)

    assert values["turn_total_tokens"] > 0
    assert values["turn_total_cost_usd"] == Decimal(0)
    usage_chunk = next(c for c in chunks if c["type"] == "data-turn-usage")
    assert usage_chunk["data"]["totalTokens"] == values["turn_total_tokens"]
    assert charges.calls == [
        (values["user_id"], values["turn_total_tokens"], Decimal(0)),
    ]


async def test_a_cancelled_turn_makes_no_further_model_call_and_finalizes() -> None:
    """The tool sets the cancel; the answer the next model call would have
    produced is never streamed, and the turn still accounts for what it used."""
    cancel = asyncio.Event()

    async def stop_now() -> str:
        """Stop the turn."""
        cancel.set()
        return "stopped"

    chunks, values = await _run(
        _tool_then_text_model("stop_now", "never streamed"),
        tools=[stop_now],
        cancel=cancel,
    )

    types = [c["type"] for c in chunks]
    assert "text-delta" not in types
    assert types[-1] == "data-turn-usage"
    assert values["turn_total_tokens"] > 0


async def test_a_cancelled_turn_still_reports_the_tool_that_already_ran() -> None:
    """A tool the cancel interrupted has already produced its result, so the
    stream carries it rather than leaving the call without an outcome."""
    cancel = asyncio.Event()

    async def stop_now() -> str:
        """Stop the turn."""
        cancel.set()
        return "stopped"

    chunks, _values = await _run(
        _tool_then_text_model("stop_now", "never streamed"),
        tools=[stop_now],
        cancel=cancel,
    )

    outputs = [c for c in chunks if c["type"] == "tool-output-available"]
    assert [c["output"] for c in outputs] == ["stopped"]
    assert outputs[0]["toolCallId"] == "call-1"
