"""Map typed ``PhaseDecision.next_action`` values to state-machine events.

The state machine at ``ai/orchestration/pipeline.py`` inherited its event
names from the pre-``output_type=`` world (``finish_scoping``,
``finish_discovery``, ``finish_planning``, ``finish_execution``,
``finish_verification``). The new ``PhaseDecision`` models use semantic
literals (``advance_to_discovery``, ``advance_to_planning``, ``complete``,
``retry``, ...) that don't match those event names.

This module is the ONE place where that translation happens. Pydantic's
discriminated unions can't help here — the event name depends on BOTH the
decision type AND its ``next_action`` literal. A per-type table keyed by
literal is the natural shape; keeping it scoped to this file means call
sites elsewhere never need to know about the legacy event names.

Returns an ordered list of events to send to the state machine. Most
decisions map to a single event, but ``PlanningDecision.advance_to_execution``
maps to two (``submit_draft`` then ``approve``) because the state machine
requires both to reach ``plan_approved`` → ``execution``. Returns an empty
tuple when the decision does NOT advance (``need_more_input`` — the turn
ends and the dispatcher loop exits gracefully).
"""

from __future__ import annotations

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.services.chat.chat_context import PhaseDecision

# Per-decision-type mappings — literal → state-machine event tuple.
# Keeping these as module-level constants keeps the dispatch function trivial.
_SCOPING_EVENTS: dict[str, tuple[str, ...]] = {
    # advance_to_planning from scoping has no direct edge; treat it the same
    # as advance_to_discovery and let discovery decide whether to short-circuit.
    "advance_to_discovery": ("finish_scoping",),
    "advance_to_planning": ("finish_scoping",),
    "need_more_input": (),
}

_DISCOVERY_EVENTS: dict[str, tuple[str, ...]] = {
    "advance_to_planning": ("finish_discovery",),
    # No direct discovery→execution edge exists; fall through to planning.
    "advance_to_execution": ("finish_discovery",),
    "need_more_input": (),
}

_PLANNING_EVENTS: dict[str, tuple[str, ...]] = {
    # planning needs two events: submit_draft → awaiting_approval,
    # approve → plan_approved (auto-advances to execution).
    "advance_to_execution": ("submit_draft", "approve"),
    "request_revision": ("submit_draft", "request_revision"),
    "abort": ("abort_planning",),
}

_EXECUTION_EVENTS: dict[str, tuple[str, ...]] = {
    "advance_to_verification": ("finish_execution",),
    "retry": ("retry",),
    "abort": ("abort_execution",),
}

_VERIFICATION_EVENTS: dict[str, tuple[str, ...]] = {
    "complete": ("finish_verification",),
    # No backwards edge verification→execution exists. End the turn; user
    # drives a fresh run on the next prompt.
    "retry_execution": ("finish_verification",),
    "abort": ("abort_verification",),
}


def events_for_decision(decision: PhaseDecision) -> tuple[str, ...]:
    """Translate a phase decision into the state-machine events that advance it.

    An empty tuple signals the dispatcher loop to stop WITHOUT marking the
    pipeline failed — used for ``need_more_input``, where the agent wants
    the user to reply before the pipeline continues.
    """
    table: dict[str, tuple[str, ...]]
    if isinstance(decision, ScopingDecision):
        table = _SCOPING_EVENTS
    elif isinstance(decision, DiscoveryDecision):
        table = _DISCOVERY_EVENTS
    elif isinstance(decision, PlanningDecision):
        table = _PLANNING_EVENTS
    elif isinstance(decision, ExecutionDecision):
        table = _EXECUTION_EVENTS
    elif isinstance(decision, VerificationDecision):
        table = _VERIFICATION_EVENTS
    else:  # pragma: no cover — Pydantic Literal validation prevents this
        msg = f"unmapped decision shape: {decision!r}"
        raise TypeError(msg)

    events = table.get(decision.next_action)
    if events is None:  # pragma: no cover — Pydantic Literal prevents this
        msg = (
            f"{type(decision).__name__} has no mapping for next_action="
            f"{decision.next_action!r}"
        )
        raise ValueError(msg)
    return events
