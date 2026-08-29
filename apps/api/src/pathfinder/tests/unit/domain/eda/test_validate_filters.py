from __future__ import annotations

from dataclasses import dataclass, field

from pathfinder.domain.eda import validate_filters

from ._facts import Ent, Study, Var


@dataclass(frozen=True)
class Sub:
    variable_id: str
    string_set: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Filt:
    entity_id: str
    variable_id: str
    type: str
    string_set: list[str] = field(default_factory=list)
    number_set: list[float] = field(default_factory=list)
    date_set: list[str] = field(default_factory=list)
    min: float | str | None = None
    max: float | str | None = None
    left: float | None = None
    right: float | None = None
    operation: str = "union"
    sub_filters: list[Sub] = field(default_factory=list)


@dataclass(frozen=True)
class BareFilt:
    entity_id: str
    variable_id: str
    type: str


def _study() -> Study:
    return Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(
            id="GENE_PHENOTYPE_DATA_ENTITY",
            variables=[
                Var(
                    id="VAR_a8ad31c0",
                    type="string",
                    display_name="Success of Genetic Modification",
                    vocabulary=["no", "yes"],
                ),
                Var(
                    id="EUPATH_0043064",
                    type="integer",
                    display_name="count",
                    data_shape="continuous",
                ),
                Var(
                    id="EUPATH_0043256",
                    type="date",
                    display_name="Collection date",
                    vocabulary=["2017-05-05", "2017-05-11"],
                ),
                Var(id="OBI_0001621", type="longitude", display_name="longitude"),
                Var(
                    id="CAT_1",
                    type="category",
                    display_name="Diagnosis",
                    display_type="multifilter",
                ),
                Var(
                    id="CHILD_1",
                    type="string",
                    display_name="Malaria",
                    parent_id="CAT_1",
                    vocabulary=["Yes"],
                ),
            ],
        ),
    )


def _ok(*filters: Filt) -> list[str]:
    return validate_filters(_study(), list(filters))


def test_a_valid_string_set_produces_no_errors() -> None:
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="VAR_a8ad31c0",
                type="stringSet",
                string_set=["yes"],
            )
        )
        == []
    )


def test_an_unknown_entity_is_reported_with_its_id() -> None:
    errors = _ok(
        Filt(entity_id="ENT_nope", variable_id="V", type="stringSet", string_set=["x"])
    )
    assert len(errors) == 1
    assert "ENT_nope" in errors[0]


def test_an_unknown_variable_is_reported_with_its_id() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_deadbeef",
            type="stringSet",
            string_set=["x"],
        )
    )
    assert len(errors) == 1
    assert "VAR_deadbeef" in errors[0]


def test_a_string_set_on_a_number_variable_names_the_expected_type() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="stringSet",
            string_set=["1"],
        )
    )
    assert len(errors) == 1
    assert "integer" in errors[0]
    assert "stringSet" in errors[0]


def test_a_number_range_on_a_longitude_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="OBI_0001621",
            type="numberRange",
            min=0.0,
            max=1.0,
        )
    )
    assert len(errors) == 1


def test_a_longitude_range_on_a_number_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="longitudeRange",
            left=0.0,
            right=1.0,
        )
    )
    assert len(errors) == 1


def test_a_string_set_on_a_category_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="stringSet",
            string_set=["Yes"],
        )
    )
    assert len(errors) == 1


def test_an_out_of_vocabulary_value_is_the_error_the_service_will_not_give() -> None:
    """Live this returns 200 with count 0, so this predicate is the only guard."""
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["maybe"],
        )
    )
    assert len(errors) == 1
    assert "maybe" in errors[0]
    assert "no" in errors[0]
    assert "yes" in errors[0]


def test_an_empty_string_set_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=[],
        )
    )
    assert len(errors) == 1


def test_a_bare_date_bound_is_refused_before_the_500() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043256",
            type="dateRange",
            min="2017-05-05",
            max="2017-05-08",
        )
    )
    assert len(errors) == 2
    assert all("T00:00:00" in e for e in errors)


def test_a_dated_bound_with_a_time_passes() -> None:
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="EUPATH_0043256",
                type="dateRange",
                min="2017-05-05T00:00:00",
                max="2017-05-08T00:00:00",
            )
        )
        == []
    )


def test_an_inverted_number_range_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="numberRange",
            min=100.0,
            max=0.0,
        )
    )
    assert len(errors) == 1
    assert "min" in errors[0]


def test_a_degenerate_longitude_window_is_refused() -> None:
    """left == right silently selects every row, so it never means what it looks like."""
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="OBI_0001621",
            type="longitudeRange",
            left=15.5,
            right=15.5,
        )
    ) == [
        "Filter longitudeRange on variable OBI_0001621 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY has left 15.5 equal to right 15.5 within "
        "1e-08, and the service reads an equal pair as a no-op that keeps every row."
    ]


def test_a_longitude_window_narrower_than_the_epsilon_is_degenerate() -> None:
    """The service compares abs(left - right) against 1e-8, not against zero."""
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="OBI_0001621",
            type="longitudeRange",
            left=15.0,
            right=15.000000001,
        )
    ) == [
        "Filter longitudeRange on variable OBI_0001621 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY has left 15.0 equal to right 15.000000001 "
        "within 1e-08, and the service reads an equal pair as a no-op that keeps "
        "every row."
    ]


def test_a_longitude_window_wider_than_the_epsilon_passes() -> None:
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="OBI_0001621",
                type="longitudeRange",
                left=15.0,
                right=15.0000001,
            )
        )
        == []
    )


def test_a_multifilter_on_a_non_multifilter_variable_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="multiFilter",
            operation="union",
            sub_filters=[Sub(variable_id="CHILD_1", string_set=["Yes"])],
        )
    )
    assert len(errors) == 1
    assert "multifilter" in errors[0]


def test_a_multifilter_sub_filter_must_be_a_child_of_the_category() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            operation="union",
            sub_filters=[Sub(variable_id="VAR_a8ad31c0", string_set=["yes"])],
        )
    )
    assert len(errors) == 1
    assert "VAR_a8ad31c0" in errors[0]


def test_a_well_formed_multifilter_passes() -> None:
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="CAT_1",
                type="multiFilter",
                operation="union",
                sub_filters=[Sub(variable_id="CHILD_1", string_set=["Yes"])],
            )
        )
        == []
    )


def test_two_disjoint_sets_on_one_single_valued_variable_are_refused() -> None:
    """The most likely way to silently produce nothing: 200 with count 0."""
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["yes"],
        ),
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["no"],
        ),
    )
    assert len(errors) == 1
    assert "one filter" in errors[0]


def test_every_error_is_reported_not_just_the_first() -> None:
    errors = _ok(
        Filt(entity_id="ENT_nope", variable_id="V", type="stringSet", string_set=["x"]),
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringSet",
            string_set=["maybe"],
        ),
    )
    assert len(errors) == 2


def test_two_overlapping_sets_on_one_single_valued_variable_pass() -> None:
    """Overlapping sets narrow to the shared members, which is a real subset."""
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="VAR_a8ad31c0",
                type="stringSet",
                string_set=["yes", "no"],
            ),
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="VAR_a8ad31c0",
                type="stringSet",
                string_set=["yes"],
            ),
        )
        == []
    )


def test_two_disjoint_sets_on_a_multi_valued_variable_pass() -> None:
    study = Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(
            id="E",
            variables=[
                Var(
                    id="VAR_035294d0",
                    vocabulary=["P. berghei", "P. falciparum"],
                    is_multi_valued=True,
                )
            ],
        ),
    )
    assert (
        validate_filters(
            study,
            [
                Filt(
                    entity_id="E",
                    variable_id="VAR_035294d0",
                    type="stringSet",
                    string_set=["P. berghei"],
                ),
                Filt(
                    entity_id="E",
                    variable_id="VAR_035294d0",
                    type="stringSet",
                    string_set=["P. falciparum"],
                ),
            ],
        )
        == []
    )


def test_an_unknown_filter_type_names_the_seven_that_exist() -> None:
    """stringPrefixSet is schema-present and wire-absent; the service answers 422."""
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="stringPrefixSet",
        )
    )
    assert len(errors) == 1
    assert "stringPrefixSet" in errors[0]
    assert "stringSet" in errors[0]
    assert "multiFilter" in errors[0]


def test_a_number_set_on_an_integer_variable_refuses_a_fractional_member() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="numberSet",
            number_set=[60.5],
        )
    )
    assert len(errors) == 1
    assert "60.5" in errors[0]


def test_a_number_set_of_whole_numbers_passes() -> None:
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="EUPATH_0043064",
                type="numberSet",
                number_set=[60.0, 61.0],
            )
        )
        == []
    )


def test_a_date_set_member_without_a_time_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043256",
            type="dateSet",
            date_set=["2017-05-05T00:00:00", "2017-05-11"],
        )
    )
    assert len(errors) == 1
    assert "T00:00:00" in errors[0]


def test_a_number_set_on_a_string_variable_is_refused() -> None:
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="numberSet",
            number_set=[1.0],
        )
    ) == [
        "Filter numberSet on variable VAR_a8ad31c0 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY is refused: the variable type is string, and "
        "numberSet applies to a variable of type integer, number."
    ]


def test_a_date_set_on_a_number_variable_is_refused() -> None:
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043064",
            type="dateSet",
            date_set=["2017-05-05T00:00:00"],
        )
    ) == [
        "Filter dateSet on variable EUPATH_0043064 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY is refused: the variable type is integer, and "
        "dateSet applies to a variable of type date."
    ]


def test_a_date_range_on_a_string_variable_is_refused() -> None:
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="VAR_a8ad31c0",
            type="dateRange",
            min="2017-05-05T00:00:00",
            max="2017-05-11T00:00:00",
        )
    ) == [
        "Filter dateRange on variable VAR_a8ad31c0 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY is refused: the variable type is string, and "
        "dateRange applies to a variable of type date."
    ]


def test_an_inverted_date_range_is_refused() -> None:
    """min above max returns count 0 with HTTP 200, exactly like a number range."""
    assert _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="EUPATH_0043256",
            type="dateRange",
            min="2017-05-11T00:00:00",
            max="2017-05-05T00:00:00",
        )
    ) == [
        "Filter dateRange on variable EUPATH_0043256 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY has min 2017-05-11T00:00:00 above max "
        "2017-05-05T00:00:00, which returns count 0 rather than an error."
    ]


def _declared(min_bound: float, max_bound: float) -> list[str]:
    return validate_filters(
        _study(),
        [
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="EUPATH_0043064",
                type="numberRange",
                min=min_bound,
                max=max_bound,
            )
        ],
        {("GENE_PHENOTYPE_DATA_ENTITY", "EUPATH_0043064"): (0.0, 20.0)},
    )


def test_bounds_that_equal_the_declared_range_pass() -> None:
    """Both declared bounds are inside the range, so the pair is exact, not outside."""
    assert _declared(0.0, 20.0) == []


def test_a_max_one_unit_above_the_declared_range_is_refused() -> None:
    assert _declared(0.0, 21.0) == [
        "Filter numberRange on variable EUPATH_0043064 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY has 21.0 outside the declared range 0.0 to 20.0."
    ]


def test_a_min_one_unit_below_the_declared_range_is_refused() -> None:
    assert _declared(-1.0, 20.0) == [
        "Filter numberRange on variable EUPATH_0043064 of entity "
        "GENE_PHENOTYPE_DATA_ENTITY has -1.0 outside the declared range 0.0 to 20.0."
    ]


def test_a_bound_outside_the_declared_range_is_reported_as_declared() -> None:
    """The bound is a hint, so the message says declared range, never invalid."""
    errors = validate_filters(
        _study(),
        [
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="EUPATH_0043064",
                type="numberRange",
                min=0.0,
                max=25.0,
            )
        ],
        {("GENE_PHENOTYPE_DATA_ENTITY", "EUPATH_0043064"): (0.0, 20.0)},
    )
    assert len(errors) == 1
    assert "declared range" in errors[0]
    assert "25.0" in errors[0]
    assert "20.0" in errors[0]


def test_the_same_bound_passes_when_no_range_is_declared() -> None:
    assert (
        _ok(
            Filt(
                entity_id="GENE_PHENOTYPE_DATA_ENTITY",
                variable_id="EUPATH_0043064",
                type="numberRange",
                min=0.0,
                max=25.0,
            )
        )
        == []
    )


def test_a_string_variable_with_no_vocabulary_accepts_any_value() -> None:
    study = Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(id="E", variables=[Var(id="FREE_TEXT")]),
    )
    assert (
        validate_filters(
            study,
            [
                Filt(
                    entity_id="E",
                    variable_id="FREE_TEXT",
                    type="stringSet",
                    string_set=["anything"],
                )
            ],
        )
        == []
    )


def test_a_fractional_member_passes_on_a_number_variable() -> None:
    study = Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(id="E", variables=[Var(id="RATE", type="number")]),
    )
    assert (
        validate_filters(
            study,
            [
                Filt(
                    entity_id="E",
                    variable_id="RATE",
                    type="numberSet",
                    number_set=[21.92],
                )
            ],
        )
        == []
    )


def test_a_long_vocabulary_is_truncated_in_the_rejection() -> None:
    """The vocabulary reaches the model as retry text, so it cannot be unbounded."""
    study = Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(
            id="E",
            variables=[
                Var(id="GENE", vocabulary=[f"PF3D7_{index:04d}" for index in range(25)])
            ],
        ),
    )
    errors = validate_filters(
        study,
        [
            Filt(
                entity_id="E",
                variable_id="GENE",
                type="stringSet",
                string_set=["PF3D7_9999"],
            )
        ],
    )
    assert len(errors) == 1
    assert "PF3D7_0019" in errors[0]
    assert "PF3D7_0020" not in errors[0]
    assert "and 5 more" in errors[0]


def test_a_category_variable_without_the_multifilter_display_is_refused() -> None:
    study = Study(
        id="STUDY_53f554ec6a",
        root_entity=Ent(
            id="E",
            variables=[
                Var(id="CAT_2", type="category", display_name="Plain group"),
                Var(id="CHILD_2", parent_id="CAT_2", vocabulary=["Yes"]),
            ],
        ),
    )
    errors = validate_filters(
        study,
        [
            Filt(
                entity_id="E",
                variable_id="CAT_2",
                type="multiFilter",
                sub_filters=[Sub(variable_id="CHILD_2", string_set=["Yes"])],
            )
        ],
    )
    assert len(errors) == 1
    assert "multifilter" in errors[0]
    assert "default" in errors[0]


def test_a_multifilter_operation_outside_the_two_the_service_knows_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            operation="xor",
            sub_filters=[Sub(variable_id="CHILD_1", string_set=["Yes"])],
        )
    )
    assert len(errors) == 1
    assert "xor" in errors[0]
    assert "union" in errors[0]
    assert "intersect" in errors[0]


def test_a_sub_filter_with_no_members_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            sub_filters=[Sub(variable_id="CHILD_1")],
        )
    )
    assert len(errors) == 1
    assert "CHILD_1" in errors[0]


def test_a_sub_filter_value_outside_the_child_vocabulary_is_refused() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            sub_filters=[Sub(variable_id="CHILD_1", string_set=["No"])],
        )
    )
    assert len(errors) == 1
    assert "No" in errors[0]
    assert "Yes" in errors[0]


def test_every_bad_sub_filter_is_reported() -> None:
    errors = _ok(
        Filt(
            entity_id="GENE_PHENOTYPE_DATA_ENTITY",
            variable_id="CAT_1",
            type="multiFilter",
            sub_filters=[
                Sub(variable_id="CHILD_1", string_set=["No"]),
                Sub(variable_id="VAR_deadbeef", string_set=["Yes"]),
            ],
        )
    )
    assert len(errors) == 2


def test_a_filter_that_carries_no_payload_is_refused_for_every_type() -> None:
    """An omitted payload key is the same 400 as an empty one."""
    bare = [
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "VAR_a8ad31c0", "stringSet"),
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "EUPATH_0043064", "numberSet"),
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "EUPATH_0043256", "dateSet"),
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "EUPATH_0043064", "numberRange"),
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "EUPATH_0043256", "dateRange"),
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "OBI_0001621", "longitudeRange"),
        BareFilt("GENE_PHENOTYPE_DATA_ENTITY", "CAT_1", "multiFilter"),
    ]
    for entry in bare:
        errors = validate_filters(_study(), [entry])
        assert len(errors) == 1, entry.type
        assert entry.type in errors[0]
