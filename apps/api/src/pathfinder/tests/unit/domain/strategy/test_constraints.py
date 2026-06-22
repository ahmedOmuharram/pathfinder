from __future__ import annotations

from pathfinder.domain.parameters.values import NumberValue
from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
    ConstraintStatus,
    GroundedConstraint,
    ground_against_plan,
    is_blocking,
    merge_constraints,
    provisional_constraints,
)
from pathfinder.domain.strategy.plan import (
    PlannedParameter,
    PlannedStep,
    StepStatus,
    StepType,
    StrategyPlan,
)


def test_constraint_defaults_to_assumed() -> None:
    c = Constraint(
        kind=ConstraintKind.DATA_TYPE, requested_value="RNA-Seq", label="data type"
    )
    assert c.source is ConstraintSource.ASSUMED


def test_blocking_only_for_user_explicit_unmet() -> None:
    explicit = Constraint(
        kind=ConstraintKind.DATA_TYPE,
        requested_value="RNA-Seq",
        source=ConstraintSource.USER_EXPLICIT,
        label="data type",
    )
    assumed = explicit.model_copy(update={"source": ConstraintSource.ASSUMED})
    ungroundable_explicit = GroundedConstraint(
        constraint=explicit, status=ConstraintStatus.UNGROUNDABLE, note="x"
    )
    substituted_explicit = GroundedConstraint(
        constraint=explicit,
        status=ConstraintStatus.SUBSTITUTED,
        realized_value="microarray",
        note="x",
    )
    grounded_explicit = GroundedConstraint(
        constraint=explicit, status=ConstraintStatus.GROUNDED, realized_value="RNA-Seq"
    )
    ungroundable_assumed = GroundedConstraint(
        constraint=assumed, status=ConstraintStatus.UNGROUNDABLE, note="x"
    )

    assert is_blocking(ungroundable_explicit) is True
    assert is_blocking(substituted_explicit) is True
    assert is_blocking(grounded_explicit) is False
    assert is_blocking(ungroundable_assumed) is False


def test_soft_user_explicit_constraint_does_not_block() -> None:
    soft = Constraint(
        kind=ConstraintKind.DATA_TYPE,
        requested_value="RNA-Seq preferred, microarray fallback ok",
        source=ConstraintSource.USER_EXPLICIT,
        label="data type",
        hard=False,
    )
    substituted = GroundedConstraint(
        constraint=soft,
        status=ConstraintStatus.SUBSTITUTED,
        realized_value="microarray",
    )
    assert is_blocking(substituted) is False


def _microarray_plan() -> StrategyPlan:
    step = PlannedStep(
        id="s2",
        search_name="GenesByMicroarrayaaegLVP_AGWG_microarrayExpression_GSE22339_male_vs_female_RSRC",
        display_name="microarray fc",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="fold_change",
                display_name="Fold change",
                param_type="number",
                value=NumberValue(value=2.0),
                status="set",
                required=True,
            )
        ],
    )
    return StrategyPlan(
        title="t", description="d", rationale="r", steps=[step], connections=[]
    )


def test_rnaseq_requested_but_microarray_used_is_substituted() -> None:
    c = Constraint(
        kind=ConstraintKind.DATA_TYPE,
        requested_value="RNA-Seq",
        source=ConstraintSource.USER_EXPLICIT,
        label="data type",
    )
    [g] = ground_against_plan([c], _microarray_plan())
    assert g.status is ConstraintStatus.SUBSTITUTED
    assert g.realized_value == "microarray"


def test_pvalue_threshold_with_no_significance_param_is_ungroundable() -> None:
    c = Constraint(
        kind=ConstraintKind.STATISTICAL_THRESHOLD,
        requested_value="adjusted p <= 0.05",
        source=ConstraintSource.USER_EXPLICIT,
        label="significance",
    )
    [g] = ground_against_plan([c], _microarray_plan())
    assert g.status is ConstraintStatus.UNGROUNDABLE
    assert g.realized_value is None


def test_fold_change_present_is_grounded() -> None:
    c = Constraint(
        kind=ConstraintKind.FOLD_CHANGE, requested_value="2", label="fold change"
    )
    [g] = ground_against_plan([c], _microarray_plan())
    assert g.status is ConstraintStatus.GROUNDED


def test_provisional_constraints_are_pending_and_non_blocking() -> None:
    c = Constraint(
        kind=ConstraintKind.DATA_TYPE,
        requested_value="RNA-Seq",
        source=ConstraintSource.USER_EXPLICIT,
        label="data type",
    )
    [g] = provisional_constraints([c])
    assert g.status is ConstraintStatus.PROVISIONAL
    assert g.realized_value is None
    assert is_blocking(g) is False


def test_merge_explicit_overrides_assumed_per_kind_and_forces_user_explicit() -> None:
    provisional = [
        Constraint(
            kind=ConstraintKind.DATA_TYPE,
            requested_value="RNA-Seq or microarray",
            label="data type",
            source=ConstraintSource.ASSUMED,
        ),
        Constraint(
            kind=ConstraintKind.ORGANISM,
            requested_value="Aedes aegypti",
            label="organism",
            source=ConstraintSource.ASSUMED,
        ),
    ]
    explicit = [
        Constraint(
            kind=ConstraintKind.DATA_TYPE,
            requested_value="RNA-Seq only",
            label="data type",
            source=ConstraintSource.ASSUMED,
        )
    ]
    merged = merge_constraints(provisional, explicit)
    by_kind = {c.kind: c for c in merged}
    assert by_kind[ConstraintKind.DATA_TYPE].requested_value == "RNA-Seq only"
    assert by_kind[ConstraintKind.DATA_TYPE].source is ConstraintSource.USER_EXPLICIT
    assert by_kind[ConstraintKind.ORGANISM].source is ConstraintSource.ASSUMED
