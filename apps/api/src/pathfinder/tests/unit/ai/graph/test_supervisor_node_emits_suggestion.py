from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import pytest
from langgraph.runtime import Runtime
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.nodes import supervisor_node
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState


def _stub_supervisor_agent(
    decision: SupervisorDecision,
) -> Agent[Any, SupervisorDecision]:
    payload: dict[str, Any] = {
        "to": decision.to,
        "reason": decision.reason,
    }
    if decision.rejection_message is not None:
        payload["rejection_message"] = decision.rejection_message
    if decision.answer is not None:
        payload["answer"] = decision.answer
    if decision.suggested_specialist is not None:
        payload["suggested_specialist"] = decision.suggested_specialist

    def _fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages, info
        return ModelResponse(parts=[
            ToolCallPart(
                tool_name="final_result",
                args=json.dumps(payload),
                tool_call_id="sup_unit",
            ),
        ])

    async def _stream(
        messages: list[ModelMessage], info: AgentInfo,
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        del messages, info
        yield {
            0: DeltaToolCall(
                name="final_result",
                json_args=json.dumps(payload),
                tool_call_id="sup_unit",
            ),
        }

    return Agent(
        FunctionModel(_fn, stream_function=_stream, model_name="mock:supervisor"),
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
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_message_id=uuid4(),
        user_prompt="is this strategy right?",
        user_parts=[TextUIPart(text="is this strategy right?", state="done")],
    )
    return base.model_copy(update=dict(overrides))


@pytest.fixture(autouse=True)
def _disable_mock_provider_override(monkeypatch: pytest.MonkeyPatch) -> None:
    real_get_settings = nodes_module.get_settings

    def _no_mock_settings() -> Any:
        settings = real_get_settings()
        return settings.model_copy(update={"pathfinder_chat_provider": ""})

    monkeypatch.setattr(nodes_module, "get_settings", _no_mock_settings)


@pytest.fixture
def capture_writer(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def _writer_payload(payload: dict[str, Any]) -> None:
        captured.append(payload)

    def _get_writer() -> Any:
        return _writer_payload

    async def _stub_resolve(state: Any, runtime: Any) -> None:
        del state, runtime

    async def _stub_render(state: PipelineState, context: Any) -> str:
        del state, context
        return "Pipeline state:\n- has_problem_frame: False"

    monkeypatch.setattr(nodes_module, "get_stream_writer", _get_writer)
    monkeypatch.setattr(nodes_module, "_resolve_supervisor_model", _stub_resolve)
    monkeypatch.setattr(nodes_module, "_render_supervisor_state", _stub_render)
    return captured


def _suggestion_chunks(captured: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for payload in captured:
        chunk = payload.get("chunk")
        if not isinstance(chunk, dict):
            continue
        if chunk.get("type") == "data-specialist-suggestion":
            out.append(chunk)
    return out


@pytest.mark.asyncio
async def test_supervisor_node_emits_suggestion_part(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = SupervisorDecision(
        to="execution",
        reason="user is asking whether the strategy works",
        suggested_specialist="validate",
    )
    monkeypatch.setattr(
        nodes_module,
        "build_supervisor_agent",
        lambda provider=None, *, model_id=None: _stub_supervisor_agent(decision),
    )
    state = _state()
    runtime = _Runtime(context=None)
    cmd = await supervisor_node(state, cast("Runtime[Context]", runtime))

    assert cmd.goto == "execution"
    chunks = _suggestion_chunks(capture_writer)
    assert len(chunks) == 1
    assert chunks[0]["data"]["kind"] == "validate"


@pytest.mark.asyncio
async def test_supervisor_node_omits_suggestion_when_unset(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = SupervisorDecision(
        to="planning",
        reason="proceed to planning",
    )
    monkeypatch.setattr(
        nodes_module,
        "build_supervisor_agent",
        lambda provider=None, *, model_id=None: _stub_supervisor_agent(decision),
    )
    state = _state()
    runtime = _Runtime(context=None)
    await supervisor_node(state, cast("Runtime[Context]", runtime))

    assert _suggestion_chunks(capture_writer) == []


@pytest.mark.asyncio
async def test_supervisor_node_emits_research_suggestion(
    capture_writer: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = SupervisorDecision(
        to="question",
        reason="open biology question",
        answer="Pf has 14 chromosomes.",
        suggested_specialist="research",
    )
    monkeypatch.setattr(
        nodes_module,
        "build_supervisor_agent",
        lambda provider=None, *, model_id=None: _stub_supervisor_agent(decision),
    )
    state = _state()
    runtime = _Runtime(context=None)
    await supervisor_node(state, cast("Runtime[Context]", runtime))

    chunks = _suggestion_chunks(capture_writer)
    assert chunks[0]["data"]["kind"] == "research"
