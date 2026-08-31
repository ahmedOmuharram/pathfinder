"""An assumed value reaches the ledger as a constraint the user can override."""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import PipelineState, StrategyDomainState
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.ledger_render import render_constraints_full
from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.strategy.constraints import (
    ConstraintKind,
    ConstraintSource,
    ConstraintStatus,
)
from pathfinder.domain.strategy.operational_spec import (
    AssumedValue,
    Criterion,
    OperationalSpec,
)

_DERISI = "GenesByMicroarrayDerisi"
_REASON = "the request says trophozoite and this window covers 17-30 hours"


def _state() -> PipelineState:
    spec = OperationalSpec(
        goal="trophozoite expression",
        interpreted_goal="trophozoite expression",
        criteria=[
            Criterion(
                id="c1",
                text="trophozoite expression",
                search_name=_DERISI,
                resolved_params={
                    "samples_percentile_generic": SinglePickValue(value="17-30h")
                },
                assumptions=[
                    AssumedValue(
                        param_name="samples_percentile_generic",
                        value="17-30h",
                        reason=_REASON,
                    )
                ],
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


def test_an_assumed_value_is_a_grounded_non_blocking_constraint() -> None:
    ledger = derive_ledger(_state(), None)

    [grounded] = ledger.constraints.grounded
    assert grounded.constraint.kind is ConstraintKind.OTHER
    assert grounded.constraint.source is ConstraintSource.ASSUMED
    assert grounded.constraint.hard is False
    assert grounded.constraint.label == "samples_percentile_generic"
    assert grounded.constraint.requested_value == "17-30h"
    assert grounded.status is ConstraintStatus.GROUNDED
    assert grounded.realized_value == "17-30h"
    assert grounded.note == _REASON
    assert ledger.constraints.blocking is False


def test_the_constraint_section_names_the_assumption() -> None:
    ledger = derive_ledger(_state(), None)

    rendered = render_constraints_full(ledger.constraints)

    assert "samples_percentile_generic" in rendered
    assert _REASON in rendered
