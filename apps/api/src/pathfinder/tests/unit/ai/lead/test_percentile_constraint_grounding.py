"""A stated share is checked against the percentile the strategy bound."""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.domain.parameters.values import NumberValue
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
    ConstraintStatus,
)
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec

_DERISI = "GenesByMicroarrayDerisi3D7SmoothedExpressionPercentile"


def _state(bound: float) -> PipelineState:
    spec = OperationalSpec(
        goal="top 10 percent of trophozoite expression",
        interpreted_goal="top 10 percent of trophozoite expression",
        constraints=[
            Constraint(
                kind=ConstraintKind.PERCENTILE,
                requested_value="top 10%",
                label="expression percentile",
                source=ConstraintSource.USER_EXPLICIT,
            )
        ],
        criteria=[
            Criterion(
                id="c1",
                text="top 10 percent of trophozoite expression",
                search_name=_DERISI,
                resolved_params={"min_expression_percentile": NumberValue(value=bound)},
            )
        ],
    )
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        domain=StrategyDomainState(operational_spec=spec),
    )


def test_a_bound_of_80_for_top_10_percent_is_substituted() -> None:
    ledger = derive_ledger(_state(80.0), None)
    [grounded] = ledger.constraints.grounded
    assert grounded.status is ConstraintStatus.SUBSTITUTED
    assert grounded.realized_value == "80"
    assert grounded.note == "bound 80 means top 20%"
    assert ledger.constraints.blocking is True


def test_a_bound_of_90_for_top_10_percent_is_grounded() -> None:
    ledger = derive_ledger(_state(90.0), None)
    [grounded] = ledger.constraints.grounded
    assert grounded.status is ConstraintStatus.GROUNDED
    assert grounded.realized_value == "90"
    assert ledger.constraints.blocking is False
