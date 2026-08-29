from __future__ import annotations

from pathfinder.domain.eda import (
    VEUPATHDB_GENE_ID,
    ancestor_entity_ids,
    entity_by_id,
    find_gene_entity,
    walk_entities,
)

from ._facts import Ent, Study, Var


def _de_study() -> Study:
    counts = Ent(
        id="ENT_fd574cd6",
        display_name="pfal3D7 htseq counts",
        variables=[
            Var(id=VEUPATHDB_GENE_ID),
            Var(id="SEQUENCE_READ_COUNT_SENSE", type="number"),
        ],
    )
    samples = Ent(
        id="ENT_8151325d",
        display_name="Samples",
        variables=[Var(id="VAR_081ab087", vocabulary=["febrile", "normal"])],
        children=[counts],
    )
    return Study(id="STUDY_e973eadd57", root_entity=samples)


def test_walk_visits_the_root_and_every_descendant() -> None:
    ids = [entity.id for entity in walk_entities(_de_study().root_entity)]
    assert ids == ["ENT_8151325d", "ENT_fd574cd6"]


def test_entity_by_id_finds_a_descendant() -> None:
    found = entity_by_id(_de_study().root_entity, "ENT_fd574cd6")
    assert found is not None
    assert found.display_name == "pfal3D7 htseq counts"


def test_entity_by_id_returns_none_for_an_unknown_id() -> None:
    assert entity_by_id(_de_study().root_entity, "ENT_nope") is None


def test_ancestors_of_a_leaf_are_every_entity_above_it() -> None:
    assert ancestor_entity_ids(_de_study().root_entity, "ENT_fd574cd6") == frozenset(
        {"ENT_8151325d"}
    )


def test_ancestors_of_the_root_are_empty() -> None:
    assert ancestor_entity_ids(_de_study().root_entity, "ENT_8151325d") == frozenset()


def test_exactly_one_gene_id_variable_resolves_the_gene_entity() -> None:
    result = find_gene_entity(_de_study())
    assert result.entity_id == "ENT_fd574cd6"
    assert result.error is None


def test_no_gene_id_variable_is_an_error_naming_the_reserved_id() -> None:
    study = Study(id="S", root_entity=Ent(id="E", variables=[Var(id="V")]))
    result = find_gene_entity(study)
    assert result.entity_id is None
    assert result.error is not None
    assert VEUPATHDB_GENE_ID in result.error


def test_two_gene_id_variables_are_an_error_naming_both_entities() -> None:
    study = Study(
        id="S",
        root_entity=Ent(
            id="A",
            variables=[Var(id=VEUPATHDB_GENE_ID)],
            children=[Ent(id="B", variables=[Var(id=VEUPATHDB_GENE_ID)])],
        ),
    )
    result = find_gene_entity(study)
    assert result.entity_id is None
    assert result.error is not None
    assert "A" in result.error
    assert "B" in result.error
