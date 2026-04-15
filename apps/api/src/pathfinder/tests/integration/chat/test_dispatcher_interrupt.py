"""Integration test: dispatcher emits data-background-task-started on interrupt."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

import pathfinder.ai.chat.dispatcher as dispatcher_module
from pathfinder.ai.chat.dispatcher import _emit_interrupt_chunks, _stream_graph_chunks
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


async def _interrupt_node(state: PipelineState) -> dict[str, Any]:
    resumed = interrupt(
        {
            "kind": "durable_task",
            "task_id": "abc-123",
            "tool_name": "run_control_tests_on_step",
            "estimated_duration_seconds": 180,
        }
    )
    return {
        "phase_decisions": {**state.phase_decisions, "scoping": resumed}
    }


def _build_interrupting_graph(checkpointer: InMemorySaver) -> Any:
    graph: StateGraph[PipelineState, Context, PipelineState, PipelineState] = (
        StateGraph(PipelineState, context_schema=Context)
    )
    graph.add_node("durable", _interrupt_node)
    graph.add_edge(START, "durable")
    graph.add_edge("durable", END)
    return graph.compile(checkpointer=checkpointer)


def _build_context(user_id: UUID) -> Context:
    return Context(
        site_id="plasmodb",
        user_id=user_id,
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=lambda: (_ for _ in ()).throw(
            AssertionError("db factory not needed")
        ),
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )


@pytest.mark.asyncio
async def test_emit_interrupt_chunks_emits_background_task_started() -> None:
    # Exercise the dispatcher's interrupt detector against a real graph
    # so the payload shape is guaranteed to match langgraph's emission.
    saver = InMemorySaver()
    graph = _build_interrupting_graph(saver)
    context = _build_context(uuid4())
    chat_id = uuid4()
    config = {"configurable": {"thread_id": str(chat_id)}}

    initial_state = PipelineState(
        chat_id=chat_id,
        user_id=context.user_id,
        site_id="plasmodb",
        mode="strategy",
    )
    emitted_interrupts: list[str] = []
    async for mode, payload in graph.astream(
        initial_state.model_dump(),
        config=config,
        context=context,
        stream_mode=["custom", "updates"],
    ):
        if mode == "updates":
            emitted_interrupts.extend(
                [sse async for sse in _emit_interrupt_chunks(payload)]
            )

    assert len(emitted_interrupts) == 1
    payload_text = emitted_interrupts[0].removeprefix("data: ").strip()
    payload_json = json.loads(payload_text)
    assert payload_json["type"] == "data-background-task-started"
    assert payload_json["data"]["taskId"] == "abc-123"
    assert payload_json["data"]["toolName"] == "run_control_tests_on_step"
    assert payload_json["data"]["estimatedDurationSeconds"] == 180


@pytest.mark.asyncio
async def test_stream_graph_chunks_yields_interrupt_sse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch generate_conversation_title so we don't fork an LLM task.
    async def _stub_title(first_user_message: str) -> str:
        del first_user_message
        return ""

    monkeypatch.setattr(
        dispatcher_module, "generate_conversation_title", _stub_title
    )

    saver = InMemorySaver()
    graph = _build_interrupting_graph(saver)
    chat_id = uuid4()
    user_id = uuid4()
    context = _build_context(user_id)

    incoming = dispatcher_module._IncomingChatRequest(
        chat_id=chat_id,
        user_message_id=uuid4(),
        user_prompt="run controls",
        user_parts=[{"type": "text", "text": "run controls"}],
        site_id="plasmodb",
        mode="strategy",
        pipeline_config=None,
        experiment_id=None,
    )

    collected: list[dict[str, Any]] = []
    async for sse in _stream_graph_chunks(
        incoming=incoming,
        user_id=user_id,
        compiled_graph=graph,
        runtime_context=context,
        title_task=None,
    ):
        if sse.startswith("data: "):
            payload_text = sse.removeprefix("data: ").strip()
            if payload_text and payload_text != "[DONE]":
                collected.append(json.loads(payload_text))

    started = [
        c for c in collected if c.get("type") == "data-background-task-started"
    ]
    assert len(started) == 1
    assert started[0]["data"]["taskId"] == "abc-123"
    assert started[0]["data"]["toolName"] == "run_control_tests_on_step"
