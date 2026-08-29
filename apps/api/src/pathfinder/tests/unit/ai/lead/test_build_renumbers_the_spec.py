"""A build re-keys the spec on the step ids it produced.

FRAME names a criterion with a label. Unless the spec adopts the step id the
build minted, the next turn's edit addresses nothing.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead import sub_agent_dispatch
from pathfinder.ai.lead.sub_agent_dispatch import build_strategy
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _spec() -> OperationalSpec:
    return OperationalSpec(
        goal="proteases",
        criteria=[
            Criterion(
                id="c1_text",
                text="protease text",
                search_name="GenesByText",
                role="seed",
                resolved_params={"organism": MultiPickValue(values=["Plasmodium"])},
            ),
            Criterion(id="c2_go", text="proteolysis GO", search_name="GenesByGoTerm"),
        ],
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                operator=CombineOp.INTERSECT,
                inputs=[
                    StructureNode(kind="leaf", criterion_id="c1_text"),
                    StructureNode(kind="leaf", criterion_id="c2_go"),
                ],
            )
        ),
    )


def _ctx(spec: OperationalSpec) -> RunContext[LeadDeps]:
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="build it",
        domain=StrategyDomainState(operational_spec=spec),
    )
    runtime = Context(
        site_id="plasmodb",
        user_id=state.user_id,
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
    )
    deps = LeadDeps(state=state, intent=None, runtime=runtime, retrieved_memories=[])
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage(), messages=[])


async def test_the_built_spec_is_re_keyed_on_the_step_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    produced: dict[str, str] = {}

    async def _fake_build(**kwargs: Any) -> BuildOutcome:
        root = kwargs["root"]
        produced["root"] = root.id
        produced["primary"] = root.primary_input.id
        produced["secondary"] = root.secondary_input.id
        return BuildOutcome(pushed_step_ids=[root.id])

    monkeypatch.setattr(sub_agent_dispatch, "build_strategy_from_spec", _fake_build)
    ctx = _ctx(_spec())

    await build_strategy(ctx)

    spec = ctx.deps.state.domain.operational_spec
    assert spec is not None
    assert {c.id for c in spec.criteria} == {produced["primary"], produced["secondary"]}
    assert spec.structure is not None
    assert [node.criterion_id for node in spec.structure.root.inputs] == [
        produced["primary"],
        produced["secondary"],
    ]
    seed = next(c for c in spec.criteria if c.search_name == "GenesByText")
    assert seed.resolved_params == {"organism": MultiPickValue(values=["Plasmodium"])}
