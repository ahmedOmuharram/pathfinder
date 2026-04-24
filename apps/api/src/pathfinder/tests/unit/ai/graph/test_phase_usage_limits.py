"""Tests for the per-phase ``UsageLimits`` cap.

Two layers:

1. **Unit** — ``_handle_usage_limit_exceeded`` directly: feed it a fake
   exception, assert the synthesized ``PhaseOutcome`` is gracefully
   shaped so the supervisor can route on it.

2. **Wiring** — ``PHASE_USAGE_LIMITS`` is actually passed into
   ``agent.run_stream_events`` (regression guard against someone
   forgetting the kwarg).
"""
from __future__ import annotations

import inspect
from uuid import uuid4

from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.graph.nodes import (
    PHASE_USAGE_LIMITS,
    _handle_usage_limit_exceeded,
    _PhaseRunCapture,
    _run_phase_node,
)
from pathfinder.ai.graph.state import (
    PhaseDisposition,
    PipelineState,
)


def _state(prose: str = "find Plasmodium kinases") -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt=prose,
    )


# ---- Unit: synthesized outcome shape ----


def test_usage_limit_handler_synthesizes_awaiting_user_outcome() -> None:
    """The supervisor distinguishes ``handoff`` (continue) from
    ``awaiting_user`` (stop). On a usage cap we MUST produce
    ``awaiting_user`` so the turn ends — otherwise the next phase
    fires and the cap was pointless."""
    capture = _PhaseRunCapture()
    exc = UsageLimitExceeded("tool_calls_limit (25) exceeded")
    _handle_usage_limit_exceeded(
        capture,
        exc,
        phase="discovery",
        state=_state(),
        agent_model="openai:gpt-4.1-mini",
    )
    assert capture.phase_outcome is not None
    assert capture.phase_outcome.disposition == PhaseDisposition.AWAITING_USER
    # Reason is for the orchestrator card — must name the phase + cause.
    assert "discovery" in capture.phase_outcome.reason.lower()
    # Prose is what the user reads — must mention the cap and offer a path forward.
    assert "discovery" in capture.phase_outcome.prose
    assert "safety budget" in capture.phase_outcome.prose
    assert "tool_calls_limit" in capture.phase_outcome.prose


def test_usage_limit_handler_does_not_double_emit_prose() -> None:
    """Phase node streams the prose itself when ``prose_already_streamed``
    is False — a synthesized outcome from a usage cap hasn't been
    streamed, so the flag must be False to ensure the user sees the
    explanation."""
    capture = _PhaseRunCapture()
    capture.prose_already_streamed = True  # Flip then verify the handler resets.
    _handle_usage_limit_exceeded(
        capture,
        UsageLimitExceeded("hit"),
        phase="execution",
        state=_state(),
        agent_model="openai:gpt-4.1-mini",
    )
    assert capture.prose_already_streamed is False


# ---- Constants: the limit values themselves ----


def test_phase_usage_limits_caps_tool_calls() -> None:
    """A finite ``tool_calls_limit`` MUST exist so a runaway loop trips a
    cap instead of burning unbounded budget. The exact value is tuned for
    legitimate discovery room — we only assert there *is* a cap and that
    it's reasonable. The token cap below is the real blast-radius guard."""
    assert isinstance(PHASE_USAGE_LIMITS, UsageLimits)
    assert PHASE_USAGE_LIMITS.tool_calls_limit is not None
    assert PHASE_USAGE_LIMITS.tool_calls_limit <= 100, (
        "tool_calls_limit feels unbounded above ~100 calls — runaway "
        "loops should hit the cap before then."
    )


def test_phase_usage_limits_caps_total_tokens_generously() -> None:
    """A token cap exists as a backstop against pathological loops, but
    it's set high enough that legitimate long discovery runs aren't
    throttled. The within-run elision processor is the primary defence;
    this is the upper-bound safety net."""
    assert PHASE_USAGE_LIMITS.total_tokens_limit is not None
    # Floor: must be high enough that real workloads don't trip it.
    assert PHASE_USAGE_LIMITS.total_tokens_limit >= 1_000_000


# ---- Wiring: the limit is actually passed in ----


def test_run_phase_node_passes_usage_limits_to_agent_stream() -> None:
    """Regression guard: someone could refactor ``_run_phase_node`` and
    forget to thread ``usage_limits=PHASE_USAGE_LIMITS`` into the
    ``agent.run_stream_events`` call. Without that kwarg the cap is
    inert. Inspect the source to fail loudly if the kwarg disappears."""
    src = inspect.getsource(_run_phase_node)
    assert "usage_limits=PHASE_USAGE_LIMITS" in src, (
        "Per-phase usage cap is not wired into agent.run_stream_events; "
        "PHASE_USAGE_LIMITS would be ignored at runtime."
    )
