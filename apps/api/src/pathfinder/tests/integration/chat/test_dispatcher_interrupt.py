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
from pathfinder.ai.chat.dispatcher import _emit_interrupt_events, _stream_graph_chunks
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_FIXED_TASK_ID = "9b4f6e6a-7e1c-4c8e-9b0a-aa1122334455"


def _parse_data_payload(frame: str) -> dict[str, Any]:
    """Extract the JSON payload from a single ``event: stream\\ndata: {...}\\n\\n`` frame."""
    payload: str | None = None
    for line in frame.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:") :].lstrip()
            break
    if payload is None:
        msg = f"frame missing data: line: {frame!r}"
        raise AssertionError(msg)
    parsed: dict[str, Any] = json.loads(payload)
    return parsed


async def _interrupt_node(state: PipelineState) -> dict[str, Any]:
    del state
    resumed = interrupt(
        {
            "kind": "durable_task",
            "task_id": _FIXED_TASK_ID,
            "tool_name": "run_control_tests_on_step",
            "estimated_duration_seconds": 180,
        }
    )
    return {"last_routing_reason": str(resumed)}


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
async def test_emit_interrupt_events_emits_background_task_started() -> None:
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
    emitted_lines: list[str] = []
    async for mode, payload in graph.astream(
        initial_state.model_dump(),
        config=config,
        context=context,
        stream_mode=["custom", "updates"],
    ):
        if mode == "updates":
            emitted_lines.extend(
                [sse async for sse in _emit_interrupt_events(payload)]
            )

    parsed = [_parse_data_payload(line) for line in emitted_lines]
    interrupts_events = [p for p in parsed if p.get("type") == "interrupts"]
    custom_events = [
        p
        for p in parsed
        if p.get("type") == "custom"
        and p.get("kind") == "data-background-task-started"
    ]
    assert len(interrupts_events) == 1
    assert len(custom_events) == 1
    assert custom_events[0]["data"]["taskId"] == _FIXED_TASK_ID
    assert custom_events[0]["data"]["toolName"] == "run_control_tests_on_step"
    assert custom_events[0]["data"]["estimatedDurationSeconds"] == 180


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

    incoming = dispatcher_module.ChatRequestBody(
        chat_id=chat_id,
        user_id=user_id,
        message="run controls",
        site_id="plasmodb",
        mode="strategy",
    )

    collected: list[dict[str, Any]] = [
        _parse_data_payload(sse)
        async for sse in _stream_graph_chunks(
            incoming=incoming,
            user_id=user_id,
            compiled_graph=graph,
            runtime_context=context,
            title_task=None,
        )
    ]

    started = [
        c
        for c in collected
        if c.get("type") == "custom"
        and c.get("kind") == "data-background-task-started"
    ]
    assert len(started) == 1
    assert started[0]["data"]["taskId"] == _FIXED_TASK_ID
    assert started[0]["data"]["toolName"] == "run_control_tests_on_step"
