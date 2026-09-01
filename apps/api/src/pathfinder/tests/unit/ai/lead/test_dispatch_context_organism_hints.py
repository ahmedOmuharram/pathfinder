"""The organisms a sub-agent reads a capped vocabulary under.

They come from the requirements the thread accumulated, in the order stated.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context, build_node_deps
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.dispatch_context import agent_deps_for
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
    organism_hints_from,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _constraint(kind: ConstraintKind, value: str) -> Constraint:
    return Constraint(
        kind=kind,
        requested_value=value,
        label=kind.value,
        source=ConstraintSource.USER_EXPLICIT,
    )


def test_only_the_organism_requirements_are_hints() -> None:
    requirements = [
        _constraint(ConstraintKind.DATA_TYPE, "RNA-Seq"),
        _constraint(ConstraintKind.ORGANISM, "Plasmodium falciparum"),
        _constraint(ConstraintKind.FOLD_CHANGE, "2"),
    ]

    assert organism_hints_from(requirements) == ["Plasmodium falciparum"]


def test_the_stated_order_is_kept() -> None:
    requirements = [
        _constraint(ConstraintKind.ORGANISM, "Plasmodium falciparum"),
        _constraint(ConstraintKind.OTHER, "kinase"),
        _constraint(ConstraintKind.ORGANISM, "Anopheles gambiae"),
    ]

    assert organism_hints_from(requirements) == [
        "Plasmodium falciparum",
        "Anopheles gambiae",
    ]


def test_a_repeated_organism_is_one_hint() -> None:
    requirements = [
        _constraint(ConstraintKind.ORGANISM, "Plasmodium falciparum"),
        _constraint(ConstraintKind.ORGANISM, "Plasmodium falciparum"),
    ]

    assert organism_hints_from(requirements) == ["Plasmodium falciparum"]


def test_no_requirement_is_no_hint() -> None:
    assert organism_hints_from([]) == []


_PROMPT = "Find P. falciparum mass-spec samples."


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _runtime() -> Context:
    return Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )


def _intent() -> UserIntent:
    return UserIntent(
        raw_text=_PROMPT,
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="mass-spec samples",
        explicit_constraints=[
            _constraint(ConstraintKind.ORGANISM, "Plasmodium falciparum")
        ],
    )


def _state() -> PipelineState:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt=_PROMPT,
        domain=StrategyDomainState(),
    )
    state.domain.record_intent(_intent(), request_text=_PROMPT)
    return state


def test_the_dispatch_deps_carry_the_organism_hints() -> None:
    deps = agent_deps_for(
        LeadDeps(
            state=_state(),
            intent=_intent(),
            runtime=_runtime(),
            retrieved_memories=[],
        )
    )

    assert deps.agent_state.organism_hints == ["Plasmodium falciparum"]


def test_the_node_deps_carry_the_organism_hints() -> None:
    deps = build_node_deps(_state(), _runtime())

    assert deps.agent_state.organism_hints == ["Plasmodium falciparum"]
