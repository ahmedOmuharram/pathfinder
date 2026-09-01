"""The state update one Lead turn writes back to the graph.

The node drives the run; this module turns what the run captured into the
delta LangGraph merges into the checkpoint.
"""

from __future__ import annotations

from typing import Any

from assistant_core.memory.schemas import MemoryValue

from pathfinder.ai.graph._lead_capture import _LeadRunCapture
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.sub_agent_tools import LeadDeps


def _domain_delta(
    *,
    deps: LeadDeps,
    capture: _LeadRunCapture,
) -> StrategyDomainState:
    domain = deps.state.domain
    next_state = (
        capture.response.next_state
        if capture.response is not None
        else domain.lead_next_state
    )
    return domain.model_copy(
        update={
            "user_intent": deps.intent,
            "discovered_searches": dict(domain.discovered_searches),
            "lead_next_state": next_state,
            # Staleness is measured against the live strategy every turn.
            "stale_build": None,
        },
    )


def _build_state_delta(
    *,
    state: PipelineState,
    deps: LeadDeps,
    capture: _LeadRunCapture,
    memories: list[MemoryValue],
) -> dict[str, Any]:
    cumulative_tokens = (
        state.turn_total_tokens + capture.tokens + capture.sub_agent_tokens
    )
    cumulative_cost = (
        state.turn_total_cost_usd + capture.cost_usd + capture.sub_agent_cost
    )
    delta: dict[str, Any] = {
        "domain": _domain_delta(deps=deps, capture=capture),
        "retrieved_memories": memories,
        "turn_total_tokens": cumulative_tokens,
        "turn_total_cost_usd": cumulative_cost,
    }
    if capture.pending_approval is not None:
        delta["pending_approval"] = capture.pending_approval
    elif capture.parked_call_answered:
        delta["pending_approval"] = None
    if capture.pending_durable_call is not None:
        delta["pending_durable_call"] = capture.pending_durable_call
    elif state.pending_durable_call is not None and capture.parked_call_answered:
        delta["pending_durable_call"] = None
    return delta


__all__ = ["_build_state_delta", "_domain_delta"]
