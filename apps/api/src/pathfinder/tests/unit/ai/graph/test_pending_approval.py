from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import pytest
from langgraph.runtime import Runtime
from pydantic_ai import Agent
from pydantic_ai.tools import DeferredToolResults, ToolDenied
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    ToolApprovalResponded,
)

import pathfinder.ai.graph.nodes as nodes_module
from pathfinder.ai.agents.supervisor import SupervisorDecision
from pathfinder.ai.graph.nodes import (
    DENY_PROSE,
    _build_deferred_tool_results,
    _is_deny_resume,
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
        user_prompt="",
        user_parts=[TextUIPart(text="", state="done")],
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


def _approve(tool_call_id: str) -> dict[str, ToolApprovalResponded]:
    return {
        tool_call_id: ToolApprovalResponded(id=tool_call_id, approved=True),
    }


def _deny(
    tool_call_id: str, reason: str | None = None,
) -> dict[str, ToolApprovalResponded]:
    return {
        tool_call_id: ToolApprovalResponded(
            id=tool_call_id, approved=False, reason=reason,
        ),
    }


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

    def test_returns_none_when_no_structured_response(self) -> None:
        # Free-text input without addToolApprovalResponse → no resume.
        state = _state(
            user_prompt="hmm let me think",
            pending_approval=_pending(tool_call_id="abc123"),
            approval_responses={},
        )
        assert _build_deferred_tool_results(state, phase="planning") is None

    def test_approves_on_structured_approve(self) -> None:
        state = _state(
            pending_approval=_pending(tool_call_id="abc123"),
            approval_responses=_approve("abc123"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        assert result.approvals == {"abc123": True}

    def test_denies_on_structured_deny_default_message(self) -> None:
        state = _state(
            pending_approval=_pending(tool_call_id="t2"),
            approval_responses=_deny("t2"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        denial = result.approvals["t2"]
        assert isinstance(denial, ToolDenied)
        assert "denied" in denial.message.lower()

    def test_denies_with_user_reason(self) -> None:
        state = _state(
            pending_approval=_pending(tool_call_id="t3"),
            approval_responses=_deny("t3", reason="want fewer steps"),
        )
        result = _build_deferred_tool_results(state, phase="planning")
        assert isinstance(result, DeferredToolResults)
        denial = result.approvals["t3"]
        assert isinstance(denial, ToolDenied)
        assert denial.message == "want fewer steps"


class TestIsDenyResume:
    def test_no_pending(self) -> None:
        assert _is_deny_resume(_state(), phase="planning") is False

    def test_phase_mismatch(self) -> None:
        state = _state(pending_approval=_pending(phase="planning"))
        assert _is_deny_resume(state, phase="execution") is False

    def test_no_response(self) -> None:
        state = _state(pending_approval=_pending(tool_call_id="t"))
        assert _is_deny_resume(state, phase="planning") is False

    def test_approved_is_not_deny(self) -> None:
        state = _state(
            pending_approval=_pending(tool_call_id="t"),
            approval_responses=_approve("t"),
        )
        assert _is_deny_resume(state, phase="planning") is False

    def test_denied_is_deny(self) -> None:
        state = _state(
            pending_approval=_pending(tool_call_id="t"),
            approval_responses=_deny("t"),
        )
        assert _is_deny_resume(state, phase="planning") is True


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
    async def test_short_circuits_to_approval_phase_on_approve(
        self,
        capture_writer: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        del capture_writer

        def _no_llm(
            provider: Any = None, *, model_id: Any = None,
        ) -> Agent[None, SupervisorDecision]:
            del provider, model_id
            msg = "supervisor must not invoke LLM when pending_approval is set"
            raise AssertionError(msg)

        monkeypatch.setattr(nodes_module, "build_supervisor_agent", _no_llm)
        state = _state(
            pending_approval=_pending(phase="planning", tool_call_id="t"),
            approval_responses=_approve("t"),
        )
        runtime = _Runtime(context=None)
        cmd = await supervisor_node(state, cast("Runtime[Context]", runtime))
        assert cmd.goto == "planning"
        update = cmd.update
        assert isinstance(update, dict)
        assert update["current_phase"] == "planning"
        assert update["supervisor_call_count"] == 1
        assert "approval" in update["last_routing_reason"].lower()

    @pytest.mark.asyncio
    async def test_records_approval_journal_entry(
        self,
        capture_writer: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            nodes_module,
            "build_supervisor_agent",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("must not be called"),
            ),
        )
        state = _state(
            pending_approval=_pending(phase="planning", tool_call_id="t"),
            approval_responses=_approve("t"),
        )
        runtime = _Runtime(context=None)
        await supervisor_node(state, cast("Runtime[Context]", runtime))
        kinds = [
            (entry.get("chunk") or {}).get("data", {}).get("kind")
            for entry in capture_writer
            if (entry.get("chunk") or {}).get("type") == "data-supervisor-context"
        ]
        assert "approval" in kinds

    @pytest.mark.asyncio
    async def test_records_deny_journal_entry(
        self,
        capture_writer: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            nodes_module,
            "build_supervisor_agent",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("must not be called"),
            ),
        )
        state = _state(
            pending_approval=_pending(phase="planning", tool_call_id="t"),
            approval_responses=_deny("t", reason="too many steps"),
        )
        runtime = _Runtime(context=None)
        await supervisor_node(state, cast("Runtime[Context]", runtime))
        kinds = [
            (entry.get("chunk") or {}).get("data", {}).get("kind")
            for entry in capture_writer
            if (entry.get("chunk") or {}).get("type") == "data-supervisor-context"
        ]
        assert "deny" in kinds

    @pytest.mark.asyncio
    async def test_does_not_resume_on_free_text(
        self,
        capture_writer: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # No structured approval response → supervisor falls through (no
        # resume short-circuit). We assert by inspecting the chunks: when
        # the resume short-circuit fires, the writer captures a
        # `data-supervisor-context` chunk with kind="approval" or "deny".
        # Without it, neither should appear before fallthrough begins.
        sentinel = "fallthrough — supervisor LLM invoked"

        def _raise_on_build(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError(sentinel)

        monkeypatch.setattr(
            nodes_module, "build_supervisor_agent", _raise_on_build,
        )
        state = _state(
            user_prompt="actually I want to think more",
            pending_approval=_pending(phase="planning", tool_call_id="t"),
            approval_responses={},
        )
        runtime = _Runtime(context=None)
        with pytest.raises(RuntimeError, match="fallthrough"):
            await supervisor_node(state, cast("Runtime[Context]", runtime))
        kinds = [
            (entry.get("chunk") or {}).get("data", {}).get("kind")
            for entry in capture_writer
            if (entry.get("chunk") or {}).get("type") == "data-supervisor-context"
        ]
        assert "approval" not in kinds
        assert "deny" not in kinds


class TestDenyShortCircuitText:
    def test_deny_prose_constant(self) -> None:
        # Sanity: the canned prose is what gets emitted on deny short-circuit.
        assert "denied" in DENY_PROSE.lower()
        assert "change" in DENY_PROSE.lower()
