from __future__ import annotations

from pathfinder.domain.strategy.constraints import (
    Constraint,
    ConstraintKind,
    ConstraintSource,
    ConstraintStatus,
    GroundedConstraint,
    ground_constraints,
    is_blocking,
    merge_constraints,
    provisional_constraints,
)

# Realized facts of a single microarray fold-change leaf — the criteria's bound
# search name, its parameter names, and the values bound to them.
_MICROARRAY_SEARCH = (
    "GenesByMicroarrayaaegLVP_AGWG_microarrayExpression_GSE22339_male_vs_female_RSRC"
)
_MICROARRAY_FACTS: dict[str, list[str] | set[str] | dict[str, str]] = {
    "search_names": [_MICROARRAY_SEARCH],
    "param_names": {"fold_change"},
    "param_values": {"fold_change": "2"},
}


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


def test_rnaseq_requested_but_microarray_used_is_substituted() -> None:
    c = Constraint(
        kind=ConstraintKind.DATA_TYPE,
        requested_value="RNA-Seq",
        source=ConstraintSource.USER_EXPLICIT,
        label="data type",
    )
    [g] = ground_constraints([c], **_MICROARRAY_FACTS)
    assert g.status is ConstraintStatus.SUBSTITUTED
    assert g.realized_value == "microarray"


def test_pvalue_threshold_with_no_significance_param_is_ungroundable() -> None:
    c = Constraint(
        kind=ConstraintKind.STATISTICAL_THRESHOLD,
        requested_value="adjusted p <= 0.05",
        source=ConstraintSource.USER_EXPLICIT,
        label="significance",
    )
    [g] = ground_constraints([c], **_MICROARRAY_FACTS)
    assert g.status is ConstraintStatus.UNGROUNDABLE
    assert g.realized_value is None


def test_fold_change_present_is_grounded() -> None:
    c = Constraint(
        kind=ConstraintKind.FOLD_CHANGE, requested_value="2", label="fold change"
    )
    [g] = ground_constraints([c], **_MICROARRAY_FACTS)
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


def _percentile(requested: str) -> Constraint:
    return Constraint(
        kind=ConstraintKind.PERCENTILE,
        requested_value=requested,
        label="expression percentile",
        source=ConstraintSource.USER_EXPLICIT,
    )


def test_a_percentile_bound_that_means_the_stated_share_is_grounded() -> None:
    [g] = ground_constraints(
        [_percentile("top 10%")],
        search_names=[_MICROARRAY_SEARCH],
        param_names={"min_expression_percentile"},
        param_values={"min_expression_percentile": "90"},
    )
    assert g.status is ConstraintStatus.GROUNDED
    assert g.realized_value == "90"


def test_a_percentile_bound_that_means_another_share_is_substituted() -> None:
    """A min percentile of 80 is the top 20 percent, not the top 10."""
    [g] = ground_constraints(
        [_percentile("top 10%")],
        search_names=[_MICROARRAY_SEARCH],
        param_names={"min_expression_percentile"},
        param_values={"min_expression_percentile": "80"},
    )
    assert g.status is ConstraintStatus.SUBSTITUTED
    assert g.realized_value == "80"
    assert g.note == "bound 80 means top 20%"
    assert is_blocking(g) is True


def test_a_bottom_share_reads_the_max_percentile_bound() -> None:
    [g] = ground_constraints(
        [_percentile("bottom 25 percent")],
        search_names=[_MICROARRAY_SEARCH],
        param_names={"max_expression_percentile"},
        param_values={"max_expression_percentile": "25"},
    )
    assert g.status is ConstraintStatus.GROUNDED


def test_a_percentile_constraint_without_a_percentile_param_is_ungroundable() -> None:
    [g] = ground_constraints(
        [_percentile("top 10%")],
        search_names=[_MICROARRAY_SEARCH],
        param_names={"fold_change"},
        param_values={"fold_change": "2"},
    )
    assert g.status is ConstraintStatus.UNGROUNDABLE
    assert g.note == "no percentile parameter in the strategy"


def test_a_percentile_request_without_a_direction_is_ungroundable() -> None:
    [g] = ground_constraints(
        [_percentile("10%")],
        search_names=[_MICROARRAY_SEARCH],
        param_names={"min_expression_percentile"},
        param_values={"min_expression_percentile": "90"},
    )
    assert g.status is ConstraintStatus.UNGROUNDABLE
    assert g.note == "the requested share and direction could not be read"
