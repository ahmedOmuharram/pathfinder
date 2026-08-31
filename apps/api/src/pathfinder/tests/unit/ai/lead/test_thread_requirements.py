"""The thread keeps what the user asked for across turns.

A clarification adds to the request; it never replaces it. The ledger and the
spec a FRAME pass starts from both carry the first turn's values.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.dispatch_context import agent_deps_for
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_MOTIF = "[TG].{5,6}YGCACACAN[TCA]H"
_TURN_ONE = (
    "Find A. gambiae midgut protease genes conserved across mosquito species "
    f"that are near the motif {_MOTIF} on the genome."
)
_TURN_TWO = (
    "Conserved = has an ortholog in at least two other mosquito species. "
    "Near = within 1 kb upstream of the motif. Go ahead."
)


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _constraint(kind: ConstraintKind, value: str, label: str) -> Constraint:
    return Constraint(
        kind=kind,
        requested_value=value,
        label=label,
        source=ConstraintSource.USER_EXPLICIT,
    )


def _turn_one_intent() -> UserIntent:
    return UserIntent(
        raw_text=_TURN_ONE,
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="midgut proteases near a motif",
        explicit_constraints=[
            _constraint(ConstraintKind.ORGANISM, "Anopheles gambiae", "organism"),
            _constraint(ConstraintKind.OTHER, _MOTIF, "regulatory motif"),
        ],
    )


def _turn_two_intent() -> UserIntent:
    return UserIntent(
        raw_text=_TURN_TWO,
        classification=IntentClassification.CLARIFICATION_RESPONSE,
        inferred_goal="confirm the definitions and proceed",
        explicit_constraints=[
            _constraint(
                ConstraintKind.OTHER, "within 1 kb upstream", "motif proximity"
            ),
        ],
    )


def _state(prompt: str) -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="vectorbase",
        mode="strategy",
        user_prompt=prompt,
        domain=StrategyDomainState(),
    )


def _deps(state: PipelineState, intent: UserIntent) -> LeadDeps:
    return LeadDeps(
        state=state,
        intent=intent,
        runtime=Context(
            site_id="vectorbase",
            user_id=uuid4(),
            strategy_session=StrategySession(site_id="vectorbase"),
            db_session_factory=_never_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
        ),
        retrieved_memories=[],
    )


def _two_turn_state() -> PipelineState:
    state = _state(_TURN_ONE)
    state.domain.record_intent(_turn_one_intent(), request_text=_TURN_ONE)
    state.user_prompt = _TURN_TWO
    state.domain.record_intent(_turn_two_intent(), request_text=_TURN_TWO)
    return state


def test_the_thread_accumulates_every_stated_requirement() -> None:
    state = _two_turn_state()

    values = [c.requested_value for c in state.domain.requirements]

    assert values == ["Anopheles gambiae", _MOTIF, "within 1 kb upstream"]


def test_a_repeated_requirement_is_recorded_once() -> None:
    state = _two_turn_state()
    state.domain.record_intent(_turn_two_intent(), request_text=_TURN_TWO)

    assert [c.requested_value for c in state.domain.requirements].count(
        "within 1 kb upstream"
    ) == 1


def test_the_clarification_turn_ledger_carries_the_first_turn_values() -> None:
    state = _two_turn_state()

    ledger = derive_ledger(state, _turn_two_intent())

    values = {g.constraint.requested_value for g in ledger.constraints.grounded}
    assert {"Anopheles gambiae", _MOTIF, "within 1 kb upstream"} <= values


def test_the_frame_deps_goal_carries_the_original_request_and_the_answer() -> None:
    state = _two_turn_state()

    goal = agent_deps_for(
        _deps(state, _turn_two_intent()),
    ).agent_state.operational_spec_draft.goal

    assert _TURN_ONE in goal
    assert _TURN_TWO in goal


def test_a_clarification_never_becomes_the_original_request() -> None:
    state = _state(_TURN_TWO)
    state.domain.record_intent(_turn_two_intent(), request_text=_TURN_TWO)
    state.user_prompt = _TURN_ONE
    state.domain.record_intent(_turn_one_intent(), request_text=_TURN_ONE)

    assert state.domain.original_request == _TURN_ONE


def test_a_new_strategy_on_an_empty_thread_starts_the_requirements_over() -> None:
    state = _two_turn_state()
    third = UserIntent(
        raw_text="Forget that. Find P. falciparum kinases.",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="kinases",
        explicit_constraints=[
            _constraint(ConstraintKind.ORGANISM, "Plasmodium falciparum", "organism"),
        ],
    )

    state.domain.record_intent(third, request_text=third.raw_text)

    assert [c.requested_value for c in state.domain.requirements] == [
        "Plasmodium falciparum"
    ]
    assert state.domain.original_request == third.raw_text


def test_a_new_strategy_on_a_built_thread_keeps_the_requirements() -> None:
    state = _two_turn_state()
    state.domain.last_build_outcome = BuildOutcome(pushed_step_ids=["s1"])
    third = UserIntent(
        raw_text="Also add the RNA-Seq filter.",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="add an arm",
    )

    state.domain.record_intent(third, request_text=third.raw_text)

    assert [c.requested_value for c in state.domain.requirements] == [
        "Anopheles gambiae",
        _MOTIF,
        "within 1 kb upstream",
    ]
    assert state.domain.original_request == _TURN_ONE


def test_the_pinned_summary_lists_every_stated_requirement() -> None:
    state = _two_turn_state()

    summary = derive_ledger(state, _turn_two_intent()).render_summary()

    assert "Anopheles gambiae" in summary
    assert _MOTIF in summary
    assert "within 1 kb upstream" in summary


def test_the_summary_caps_the_requirement_list() -> None:
    state = _state("many requirements")
    intent = UserIntent(
        raw_text="many requirements",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="many",
        explicit_constraints=[
            _constraint(ConstraintKind.OTHER, f"requirement {i}", f"r{i}")
            for i in range(30)
        ],
    )
    state.domain.record_intent(intent, request_text="many requirements")

    summary = derive_ledger(state, intent).render_summary()

    assert summary.count("requirement ") == 20
    assert "10 more stated earlier" in summary
