from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import (
    ConstraintCheck,
    PhaseDisposition,
    PipelineState,
    StrategyDomainState,
    VerificationDigest,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.domain.parameters.values import NumberValue
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
    ConstraintStatus,
)
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
)

_MICROARRAY_SEARCH = (
    "GenesByMicroarrayaaegLVP_AGWG_microarrayExpression_GSE22339_male_vs_female_RSRC"
)


def _microarray_spec(constraints: list[Constraint]) -> OperationalSpec:
    return OperationalSpec(
        goal="g",
        interpreted_goal="g",
        constraints=constraints,
        criteria=[
            Criterion(
                id="c1",
                text="microarray fold change",
                search_name=_MICROARRAY_SEARCH,
                resolved_params={"fold_change": NumberValue(value=2.0)},
            ),
        ],
    )


def _state_with_constraint(source: ConstraintSource) -> PipelineState:
    spec = _microarray_spec(
        [
            Constraint(
                kind=ConstraintKind.DATA_TYPE,
                requested_value="RNA-Seq",
                source=source,
                label="data type",
            )
        ]
    )
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="vectorbase",
        mode="strategy",
        domain=StrategyDomainState(operational_spec=spec),
    )


def test_ledger_constraints_block_when_user_explicit_unmet() -> None:
    ledger = derive_ledger(_state_with_constraint(ConstraintSource.USER_EXPLICIT), None)
    assert ledger.constraints.blocking is True
    assert ledger.constraints.unmet_count == 1
    assert any(
        g.status is ConstraintStatus.SUBSTITUTED for g in ledger.constraints.grounded
    )


def test_ledger_constraints_not_blocking_for_assumed() -> None:
    ledger = derive_ledger(_state_with_constraint(ConstraintSource.ASSUMED), None)
    assert ledger.constraints.blocking is False


def test_render_summary_surfaces_blocking_constraints() -> None:
    ledger = derive_ledger(_state_with_constraint(ConstraintSource.USER_EXPLICIT), None)
    summary = ledger.render_summary()
    assert "## Constraints" in summary
    assert "blocking: True" in summary


def test_explicit_turn_constraint_overrides_assumed_spec_and_blocks() -> None:
    spec = _microarray_spec(
        [
            Constraint(
                kind=ConstraintKind.DATA_TYPE,
                requested_value="RNA-Seq or microarray",
                source=ConstraintSource.ASSUMED,
                label="data type",
            )
        ]
    )
    intent = UserIntent(
        raw_text="RNA-Seq only — hard requirement, do not use microarray",
        classification=IntentClassification.CLARIFICATION_RESPONSE,
        inferred_goal="female-enriched OBPs via RNA-Seq",
        explicit_constraints=[
            Constraint(
                kind=ConstraintKind.DATA_TYPE,
                requested_value="RNA-Seq",
                source=ConstraintSource.USER_EXPLICIT,
                label="data type",
            )
        ],
    )
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="vectorbase",
        mode="strategy",
        domain=StrategyDomainState(operational_spec=spec),
    )
    ledger = derive_ledger(state, intent)
    assert ledger.constraints.blocking is True
    assert ledger.constraints.unmet_count == 1
    data_type = next(
        g
        for g in ledger.constraints.grounded
        if g.constraint.kind is ConstraintKind.DATA_TYPE
    )
    assert data_type.status is ConstraintStatus.SUBSTITUTED
    assert data_type.constraint.source is ConstraintSource.USER_EXPLICIT


def test_constraints_surface_as_provisional_when_no_spec_yet() -> None:
    intent = UserIntent(
        raw_text="RNA-Seq only",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="x",
        explicit_constraints=[
            Constraint(
                kind=ConstraintKind.DATA_TYPE,
                requested_value="RNA-Seq only",
                source=ConstraintSource.USER_EXPLICIT,
                label="data type",
            )
        ],
    )
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="vectorbase",
        mode="strategy",
    )
    ledger = derive_ledger(state, intent)
    assert len(ledger.constraints.grounded) == 1
    assert ledger.constraints.grounded[0].status is ConstraintStatus.PROVISIONAL
    assert ledger.constraints.blocking is False


def test_verification_digest_carries_constraint_report() -> None:
    d = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="p",
        reason="r",
        success=False,
        constraint_report=[
            ConstraintCheck(
                label="data type",
                requested="RNA-Seq",
                realized="microarray",
                honored=False,
                note="RNA-Seq unavailable (WDK 500); used microarray GSE22339",
            )
        ],
    )
    assert d.constraint_report[0].honored is False


def test_operational_spec_carries_typed_constraints() -> None:
    spec = _microarray_spec(
        [
            Constraint(
                kind=ConstraintKind.DATA_TYPE,
                requested_value="RNA-Seq",
                source=ConstraintSource.USER_EXPLICIT,
                label="data type",
            )
        ]
    )
    assert spec.constraints[0].kind is ConstraintKind.DATA_TYPE
    round_trip = OperationalSpec.model_validate(spec.model_dump(by_alias=True))
    assert round_trip.constraints[0].source is ConstraintSource.USER_EXPLICIT
