from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import pytest
from langgraph.runtime import Runtime
from pydantic_ai import Agent
from pydantic_ai.tools import DeferredToolResults, ToolDenied

import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.nodes import (
    _build_deferred_tool_results,
    _resume_user_prompt,
    supervisor_node,
)
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import (
    PendingApproval,
    PipelineState,
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
        user_prompt="approved",
        user_parts=[{"type": "text", "text": "approved"}],
    )
    return base.model_copy(update=dict(overrides))


def _pending(
    phase: str = "planning",
    tool_call_id: str = "call_xyz",
) -> PendingApproval:
    return PendingApproval(
        phase=phase,  # type: ignore[arg-type]
        tool_call_id=tool_call_id,
        tool_name="submit_plan",
    )


@pytest.fixture
def capture_writer(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    captured: list[dict[str, Any]] = []

    def _writer_payload(payload: dict[str, Any]) -> None:
        captured.append(payload)

    def _get_writer() -> Any:
        return _writer_payload

    monkeypatch.setattr(nodes_module, "get_stream_writer", _get_writer)
    return captured


class TestBuildDeferredToolResults:
    def test_returns_none_when_no_pending(self) -> None:
        state = _state(pending_approval=None)
        assert _build_deferred_tool_results(state, phase="planning") is None

    def test_returns_none_on_phase_mismatch(self) -> None:
        state = _state(pending_approval=_pending(phase="planning"))
        assert _build_deferred_tool_results(state, phase="execution") is None

    def test_approves_on_yes(self) -> None:
        state = _state(
            user_prompt="yes",
            pending_approval=_pending(tool_call_id="abc123"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        assert result.approvals == {"abc123": True}

    def test_approves_on_proceed(self) -> None:
        state = _state(
            user_prompt="Looks good, please proceed.",
            pending_approval=_pending(tool_call_id="t1"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        assert result.approvals == {"t1": True}

    def test_denies_on_change_request(self) -> None:
        state = _state(
            user_prompt="Change step 3 to use P. vivax",
            pending_approval=_pending(tool_call_id="t2"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        denial = result.approvals["t2"]
        assert isinstance(denial, ToolDenied)
        assert "P. vivax" in denial.message

    def test_denies_on_explicit_no(self) -> None:
        state = _state(
            user_prompt="no",
            pending_approval=_pending(tool_call_id="t3"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        assert isinstance(result.approvals["t3"], ToolDenied)


class TestResumeUserPrompt:
    def test_returns_user_prompt_when_no_approval(self) -> None:
        state = _state(user_prompt="some new question")
        assert _resume_user_prompt(state) == "some new question"

    def test_returns_none_when_approval_pending(self) -> None:
        state = _state(
            user_prompt="yes",
            pending_approval=_pending(),
        )
        assert _resume_user_prompt(state) is None


class TestSupervisorShortCircuit:
    @pytest.mark.asyncio
    async def test_short_circuits_to_approval_phase(
        self,
        capture_writer: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        del capture_writer

        def _no_llm(
            provider: Any = None,
            *,
            model_id: Any = None,
        ) -> Agent[None, SupervisorDecision]:
            del provider, model_id
            msg = "supervisor must not invoke LLM when pending_approval is set"
            raise AssertionError(msg)

        monkeypatch.setattr(nodes_module, "build_supervisor_agent", _no_llm)
        state = _state(
            user_prompt="approved",
            pending_approval=_pending(phase="planning"),
        )
        runtime = _Runtime(context=None)
        cmd = await supervisor_node(state, cast("Runtime[Context]", runtime))
        assert cmd.goto == "planning"
        update = cmd.update
        assert isinstance(update, dict)
        assert update["current_phase"] == "planning"
        assert update["supervisor_call_count"] == 1
        assert "approval" in update["last_routing_reason"].lower()
