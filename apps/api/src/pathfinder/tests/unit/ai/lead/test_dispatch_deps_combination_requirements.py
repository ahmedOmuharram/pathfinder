"""The stated combinations a sub-agent checks its own tree against.

They travel on the sub-agent's tool state, because the gate runs inside
``set_structure`` and never reads the pipeline state.
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
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

_PROMPT = "Kinases with mass spec evidence or DeRisi expression."
_EXPRESSION = "mass spectrometry evidence OR DeRisi expression"


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
        inferred_goal="kinase drug targets",
        explicit_constraints=[
            Constraint(
                kind=ConstraintKind.ORGANISM,
                requested_value="Plasmodium falciparum",
                label="organism",
                source=ConstraintSource.USER_EXPLICIT,
            ),
            Constraint(
                kind=ConstraintKind.COMBINATION,
                requested_value=_EXPRESSION,
                label="how the evidence combines",
                source=ConstraintSource.USER_EXPLICIT,
            ),
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


def test_the_dispatch_deps_carry_the_combination_requirements() -> None:
    deps = agent_deps_for(
        LeadDeps(
            state=_state(),
            intent=_intent(),
            runtime=_runtime(),
            retrieved_memories=[],
        )
    )

    assert [c.requested_value for c in deps.agent_state.combination_requirements] == [
        _EXPRESSION
    ]


def test_the_node_deps_carry_the_combination_requirements() -> None:
    deps = build_node_deps(_state(), _runtime())

    assert [c.requested_value for c in deps.agent_state.combination_requirements] == [
        _EXPRESSION
    ]
