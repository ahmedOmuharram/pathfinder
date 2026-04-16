from __future__ import annotations

import inspect
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from langgraph.graph import END
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.nodes import SUPERVISOR_CALL_BUDGET, supervisor_node
from pathfinder.ai.graph.state import PipelineState


def test_supervisor_decision_validates_target() -> None:
    d = SupervisorDecision(to="planning", reason="plan ready")
    assert d.to == "planning"


def test_supervisor_decision_rejects_unknown_target() -> None:
    with pytest.raises(ValidationError):
        SupervisorDecision.model_validate({"to": "teleport", "reason": "x"})


def test_supervisor_decision_requires_reason() -> None:
    with pytest.raises(ValidationError):
        SupervisorDecision.model_validate({"to": "scoping", "reason": ""})


def _stub_supervisor_agent(decision: SupervisorDecision) -> Agent[None, SupervisorDecision]:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[
            ToolCallPart(
                tool_name="final_result",
                args=json.dumps({"to": decision.to, "reason": decision.reason}),
                tool_call_id="sup_unit",
            )
        ])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield {
            0: DeltaToolCall(
                name="final_result",
                json_args=json.dumps({"to": decision.to, "reason": decision.reason}),
                tool_call_id="sup_unit",
            )
        }

    return Agent(
        FunctionModel(_fn, stream_function=_stream, model_name="mock/supervisor"),
        output_type=SupervisorDecision,
        instructions="x",
        name="mock-supervisor",
        defer_model_check=True,
    )


@dataclass
class _Runtime:
    context: Any


def _state(**overrides: Any) -> PipelineState:
    base = PipelineState(
        chat_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_message_id=uuid4(),
        user_prompt="hello",
        user_parts=[{"type": "text", "text": "hello"}],
    )
    return base.model_copy(update=dict(overrides))


@pytest.fixture
def capture_writer(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def _writer_payload(payload: dict[str, Any]) -> None:
        captured.append(payload)

    def _get_writer() -> Any:
        return _writer_payload

    monkeypatch.setattr(nodes_module, "get_stream_writer", _get_writer)
    return captured


def _phase_change_events(
    captured: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for payload in captured:
        ev = payload.get("stream_event")
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "custom" and ev.get("kind") == "data-phase-change":
            out.append(ev["data"])
    return out


@pytest.mark.asyncio
async def test_first_turn_short_circuits_to_scoping_without_llm(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_llm(provider: Any = None) -> Agent[None, SupervisorDecision]:
        del provider
        msg = "supervisor LLM should not be invoked on first call"
        raise AssertionError(msg)

    monkeypatch.setattr(nodes_module, "build_supervisor_agent", _no_llm)
    state = _state()
    runtime = _Runtime(context=None)
    cmd = await supervisor_node(state, runtime)  # type: ignore[arg-type]
    assert cmd.goto == "scoping"
    update = cmd.update
    assert isinstance(update, dict)
    assert update["current_phase"] == "scoping"
    assert update["supervisor_call_count"] == 1
    assert "turn start" in update["last_routing_reason"]
    chips = _phase_change_events(capture_writer)
    assert any(c["phase"] == "scoping" and c["status"] == "started" for c in chips)


@pytest.mark.asyncio
async def test_supervisor_routes_via_llm_decision(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = SupervisorDecision(to="planning", reason="discovery is sufficient")
    monkeypatch.setattr(
        nodes_module,
        "build_supervisor_agent",
        lambda provider=None: _stub_supervisor_agent(decision),
    )
    state = _state(
        supervisor_call_count=2,
        current_phase="discovery",
        last_assistant_prose="found candidates A and B",
    )
    runtime = _Runtime(context=None)
    cmd = await supervisor_node(state, runtime)  # type: ignore[arg-type]
    assert cmd.goto == "planning"
    update = cmd.update
    assert isinstance(update, dict)
    assert update["current_phase"] == "planning"
    assert update["supervisor_call_count"] == 3
    assert update["last_routing_reason"] == "discovery is sufficient"
    chips = _phase_change_events(capture_writer)
    chip = next(c for c in chips if c["phase"] == "planning")
    assert chip["status"] == "started"
    assert chip["reason"] == "discovery is sufficient"


@pytest.mark.asyncio
async def test_supervisor_end_target_routes_to_end(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = SupervisorDecision(to="end", reason="user can take it from here")
    monkeypatch.setattr(
        nodes_module,
        "build_supervisor_agent",
        lambda provider=None: _stub_supervisor_agent(decision),
    )
    state = _state(supervisor_call_count=1, current_phase="scoping")
    runtime = _Runtime(context=None)
    cmd = await supervisor_node(state, runtime)  # type: ignore[arg-type]
    assert cmd.goto == END
    update = cmd.update
    assert isinstance(update, dict)
    assert update["last_routing_reason"] == "user can take it from here"
    assert "current_phase" not in update
    chips = _phase_change_events(capture_writer)
    chip = next(c for c in chips if c["phase"] == "completed")
    assert chip["status"] == "completed"
    assert chip["reason"] == "user can take it from here"


@pytest.mark.asyncio
async def test_supervisor_budget_exhaustion_forces_end(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_llm(provider: Any = None) -> Agent[None, SupervisorDecision]:
        del provider
        msg = "budget abort must not invoke the LLM"
        raise AssertionError(msg)

    monkeypatch.setattr(nodes_module, "build_supervisor_agent", _no_llm)
    state = _state(
        supervisor_call_count=SUPERVISOR_CALL_BUDGET,
        current_phase="execution",
    )
    runtime = _Runtime(context=None)
    cmd = await supervisor_node(state, runtime)  # type: ignore[arg-type]
    assert cmd.goto == END
    update = cmd.update
    assert isinstance(update, dict)
    assert "budget" in update["last_routing_reason"].lower()
    chips = _phase_change_events(capture_writer)
    chip = next(c for c in chips if c["status"] == "failed")
    assert "budget" in chip["reason"].lower()


@pytest.mark.asyncio
async def test_supervisor_falls_back_to_end_on_llm_failure(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        msg = "boom"
        raise RuntimeError(msg)

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        if False:
            yield ""
        msg = "boom"
        raise RuntimeError(msg)

    boom_agent: Agent[None, SupervisorDecision] = Agent(
        FunctionModel(_fn, stream_function=_stream, model_name="mock/boom"),
        output_type=SupervisorDecision,
        instructions="x",
        name="boom-supervisor",
        defer_model_check=True,
        retries=0,
    )
    monkeypatch.setattr(
        nodes_module, "build_supervisor_agent", lambda provider=None: boom_agent,
    )
    state = _state(supervisor_call_count=1, current_phase="scoping")
    runtime = _Runtime(context=None)
    cmd = await supervisor_node(state, runtime)  # type: ignore[arg-type]
    assert cmd.goto == END
    update = cmd.update
    assert isinstance(update, dict)
    assert "ending turn" in update["last_routing_reason"]
    assert inspect.iscoroutinefunction(supervisor_node)
