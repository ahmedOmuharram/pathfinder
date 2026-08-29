from __future__ import annotations

from dataclasses import dataclass, field

from pathfinder.domain.eda import VEUPATHDB_GENE_ID, validate_compute_config

from ._facts import Ent, Study, Var


@dataclass(frozen=True)
class Spec:
    entity_id: str
    variable_id: str


@dataclass(frozen=True)
class Group:
    label: str


@dataclass(frozen=True)
class Comparator:
    variable: Spec
    group_a: list[Group] = field(default_factory=list)
    group_b: list[Group] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    identifier_variable: Spec
    value_variable: Spec
    comparator: Comparator
    differential_expression_method: str = "DESeq"


def _study() -> Study:
    counts = Ent(
        id="ENT_fd574cd6",
        variables=[
            Var(id=VEUPATHDB_GENE_ID),
            Var(id="SEQUENCE_READ_COUNT_SENSE", type="number"),
        ],
    )
    return Study(
        id="STUDY_e973eadd57",
        root_entity=Ent(
            id="ENT_8151325d",
            variables=[
                Var(
                    id="VAR_081ab087",
                    display_name="temperature",
                    vocabulary=["febrile", "normal"],
                )
            ],
            children=[counts],
        ),
    )


def _config(**overrides: object) -> Config:
    base = Config(
        identifier_variable=Spec("ENT_fd574cd6", VEUPATHDB_GENE_ID),
        value_variable=Spec("ENT_fd574cd6", "SEQUENCE_READ_COUNT_SENSE"),
        comparator=Comparator(
            variable=Spec("ENT_8151325d", "VAR_081ab087"),
            group_a=[Group("normal")],
            group_b=[Group("febrile")],
        ),
    )
    return Config(**{**base.__dict__, **overrides})


def test_the_measured_working_configuration_is_accepted() -> None:
    assert validate_compute_config(_study(), _config()) == []


def test_the_two_input_variables_must_share_an_entity() -> None:
    """A different entity is accepted at submit and the job then fails."""
    errors = validate_compute_config(
        _study(),
        _config(value_variable=Spec("ENT_8151325d", "VAR_081ab087")),
    )
    assert len(errors) == 1
    assert "same entity" in errors[0]


def test_the_comparator_variable_must_sit_on_an_ancestor_entity() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_fd574cd6", "SEQUENCE_READ_COUNT_SENSE"),
                group_a=[Group("a")],
                group_b=[Group("b")],
            )
        ),
    )
    assert any("ancestor" in e for e in errors)


def test_a_group_label_outside_the_vocabulary_is_refused() -> None:
    """Accepted at submit; the job then produces a wrong or empty answer."""
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[Group("NOT_A_VALUE")],
                group_b=[Group("febrile")],
            )
        ),
    )
    assert len(errors) == 1
    assert "NOT_A_VALUE" in errors[0]
    assert "febrile" in errors[0]


def test_an_empty_group_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[],
                group_b=[Group("febrile")],
            )
        ),
    )
    assert any("groupA" in e for e in errors)


def test_the_two_groups_may_not_share_a_label() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[Group("normal")],
                group_b=[Group("normal")],
            )
        ),
    )
    assert any("both groups" in e for e in errors)


def test_deseq2_is_refused_with_the_two_wire_values_named() -> None:
    errors = validate_compute_config(
        _study(), _config(differential_expression_method="DESeq2")
    )
    assert len(errors) == 1
    assert "DESeq" in errors[0]
    assert "limma" in errors[0]


def test_an_identifier_variable_that_is_not_the_reserved_gene_id_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(identifier_variable=Spec("ENT_fd574cd6", "SEQUENCE_READ_COUNT_SENSE")),
    )
    assert any(VEUPATHDB_GENE_ID in e for e in errors)


def test_a_value_variable_outside_the_reserved_ids_is_refused() -> None:
    study = Study(
        id="S",
        root_entity=Ent(
            id="P",
            variables=[Var(id="C", vocabulary=["a", "b"])],
            children=[
                Ent(
                    id="E",
                    variables=[
                        Var(id=VEUPATHDB_GENE_ID),
                        Var(id="MADE_UP", type="number"),
                    ],
                )
            ],
        ),
    )
    errors = validate_compute_config(
        study,
        Config(
            identifier_variable=Spec("E", VEUPATHDB_GENE_ID),
            value_variable=Spec("E", "MADE_UP"),
            comparator=Comparator(
                variable=Spec("P", "C"),
                group_a=[Group("a")],
                group_b=[Group("b")],
            ),
        ),
    )
    assert any("SEQUENCE_READ_COUNT" in e for e in errors)


def test_limma_is_accepted() -> None:
    assert (
        validate_compute_config(
            _study(), _config(differential_expression_method="limma")
        )
        == []
    )


def test_an_empty_group_b_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_081ab087"),
                group_a=[Group("normal")],
                group_b=[],
            )
        ),
    )
    assert any("groupB" in e for e in errors)


def test_an_input_entity_the_study_does_not_carry_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(identifier_variable=Spec("ENT_nope", VEUPATHDB_GENE_ID)),
    )
    assert len(errors) == 1
    assert "ENT_nope" in errors[0]
    assert "identifierVariable" in errors[0]


def test_a_comparator_variable_the_entity_does_not_declare_is_refused() -> None:
    errors = validate_compute_config(
        _study(),
        _config(
            comparator=Comparator(
                variable=Spec("ENT_8151325d", "VAR_deadbeef"),
                group_a=[Group("normal")],
                group_b=[Group("febrile")],
            )
        ),
    )
    assert len(errors) == 1
    assert "VAR_deadbeef" in errors[0]
    assert "comparator.variable" in errors[0]


def test_a_category_comparator_variable_is_refused() -> None:
    """A category groups other variables, so it has no values a label can name."""
    study = Study(
        id="S",
        root_entity=Ent(
            id="P",
            variables=[
                Var(id="CAT_C", type="category", display_type="multifilter"),
                Var(id="CHILD_C", parent_id="CAT_C", vocabulary=["Yes"]),
            ],
            children=[
                Ent(
                    id="E",
                    variables=[
                        Var(id=VEUPATHDB_GENE_ID),
                        Var(id="SEQUENCE_READ_COUNT", type="integer"),
                    ],
                )
            ],
        ),
    )
    assert validate_compute_config(
        study,
        Config(
            identifier_variable=Spec("E", VEUPATHDB_GENE_ID),
            value_variable=Spec("E", "SEQUENCE_READ_COUNT"),
            comparator=Comparator(
                variable=Spec("P", "CAT_C"),
                group_a=[Group("Yes")],
                group_b=[Group("No")],
            ),
        ),
    ) == [
        "comparator.variable names CAT_C, which is a category variable. A category "
        "groups other variables and holds no values, so no label can name a side "
        "of the comparison."
    ]


def test_a_comparator_variable_with_no_vocabulary_accepts_any_label() -> None:
    study = Study(
        id="S",
        root_entity=Ent(
            id="P",
            variables=[Var(id="FREE_TEXT")],
            children=[
                Ent(
                    id="E",
                    variables=[
                        Var(id=VEUPATHDB_GENE_ID),
                        Var(id="SEQUENCE_READ_COUNT", type="integer"),
                    ],
                )
            ],
        ),
    )
    assert (
        validate_compute_config(
            study,
            Config(
                identifier_variable=Spec("E", VEUPATHDB_GENE_ID),
                value_variable=Spec("E", "SEQUENCE_READ_COUNT"),
                comparator=Comparator(
                    variable=Spec("P", "FREE_TEXT"),
                    group_a=[Group("anything")],
                    group_b=[Group("else")],
                ),
            ),
        )
        == []
    )
