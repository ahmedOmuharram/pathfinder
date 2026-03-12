"""Unit tests for seed definitions across all per-database modules."""

import pytest

from veupath_chatbot.services.experiment.seed.seeds import (
    SEED_DATABASES,
    get_all_seeds,
    get_seeds_for_site,
)
from veupath_chatbot.services.experiment.seed.types import ControlSetDef, SeedDef

SEEDS = get_all_seeds()


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestControlSetDef:
    def test_fields(self):
        cs = ControlSetDef(
            name="Test",
            positive_ids=["a", "b"],
            negative_ids=["c"],
            provenance_notes="notes",
            tags=["tag1"],
        )
        assert cs.name == "Test"
        assert cs.positive_ids == ["a", "b"]
        assert cs.negative_ids == ["c"]
        assert cs.provenance_notes == "notes"
        assert cs.tags == ["tag1"]

    def test_tags_default_empty(self):
        cs = ControlSetDef(
            name="X",
            positive_ids=[],
            negative_ids=[],
            provenance_notes="",
        )
        assert cs.tags == []


class TestSeedDef:
    def test_fields(self):
        sd = SeedDef(
            name="Test Seed",
            description="A test",
            site_id="plasmodb",
            step_tree={"id": "s1"},
            control_set=ControlSetDef(
                name="CS",
                positive_ids=["p1"],
                negative_ids=["n1"],
                provenance_notes="notes",
            ),
        )
        assert sd.name == "Test Seed"
        assert sd.site_id == "plasmodb"
        assert sd.record_type == "transcript"

    def test_record_type_override(self):
        sd = SeedDef(
            name="X",
            description="",
            site_id="toxodb",
            step_tree={},
            control_set=ControlSetDef(
                name="CS", positive_ids=[], negative_ids=[], provenance_notes=""
            ),
            record_type="gene",
        )
        assert sd.record_type == "gene"


# ---------------------------------------------------------------------------
# Per-database loading
# ---------------------------------------------------------------------------


class TestSeedLoading:
    def test_seed_databases_non_empty(self):
        assert len(SEED_DATABASES) > 0

    @pytest.mark.parametrize("site_id", SEED_DATABASES)
    def test_each_site_loads_seeds(self, site_id):
        seeds = get_seeds_for_site(site_id)
        assert len(seeds) > 0, f"No seeds for site {site_id}"

    @pytest.mark.parametrize("site_id", SEED_DATABASES)
    def test_each_site_returns_seed_defs(self, site_id):
        seeds = get_seeds_for_site(site_id)
        for seed in seeds:
            assert isinstance(seed, SeedDef), f"Expected SeedDef, got {type(seed)}"

    def test_get_all_seeds_combines_all_sites(self):
        all_seeds = get_all_seeds()
        site_ids = {s.site_id for s in all_seeds}
        for db in SEED_DATABASES:
            assert db in site_ids, f"Site {db} missing from get_all_seeds()"


# ---------------------------------------------------------------------------
# SEEDS structural validation
# ---------------------------------------------------------------------------


class TestSeedsList:
    def test_seeds_is_non_empty(self):
        assert len(SEEDS) > 0

    def test_all_seeds_are_seed_def(self):
        for seed in SEEDS:
            assert isinstance(seed, SeedDef), f"Expected SeedDef, got {type(seed)}"

    def test_all_seeds_have_required_fields(self):
        for seed in SEEDS:
            assert seed.name, "Seed missing name"
            assert seed.description, f"Seed '{seed.name}' missing description"
            assert seed.site_id, f"Seed '{seed.name}' missing site_id"
            assert seed.step_tree, f"Seed '{seed.name}' missing step_tree"
            assert seed.control_set, f"Seed '{seed.name}' missing control_set"

    def test_all_control_sets_have_positive_and_negative(self):
        for seed in SEEDS:
            cs = seed.control_set
            assert len(cs.positive_ids) > 0, (
                f"Seed '{seed.name}' has no positive controls"
            )
            assert len(cs.negative_ids) > 0, (
                f"Seed '{seed.name}' has no negative controls"
            )

    def test_all_control_sets_no_overlap(self):
        for seed in SEEDS:
            cs = seed.control_set
            overlap = set(cs.positive_ids) & set(cs.negative_ids)
            assert len(overlap) == 0, (
                f"Seed '{seed.name}' has overlapping controls: {overlap}"
            )

    def test_all_step_trees_have_id(self):
        for seed in SEEDS:
            assert "id" in seed.step_tree, f"Seed '{seed.name}' step_tree missing 'id'"

    def test_all_seed_site_ids_in_database_list(self):
        for seed in SEEDS:
            assert seed.site_id in SEED_DATABASES, (
                f"Seed '{seed.name}' has unknown site_id: {seed.site_id}"
            )

    def test_all_seed_names_unique(self):
        names = [s.name for s in SEEDS]
        assert len(names) == len(set(names)), "Duplicate seed names found"

    def test_step_tree_leaf_nodes_have_search_name(self):
        """Every leaf node in a step tree must have a searchName."""

        def _check_leaves(node, seed_name):
            has_primary = "primaryInput" in node
            has_secondary = "secondaryInput" in node
            if not has_primary and not has_secondary:
                assert "searchName" in node, (
                    f"Seed '{seed_name}' leaf node '{node.get('id')}' "
                    f"missing searchName"
                )
            if has_primary:
                _check_leaves(node["primaryInput"], seed_name)
            if has_secondary:
                _check_leaves(node["secondaryInput"], seed_name)

        for seed in SEEDS:
            _check_leaves(seed.step_tree, seed.name)

    def test_combine_nodes_have_operator(self):
        """Any node with both primaryInput and secondaryInput must have an operator."""

        def _check_operators(node, seed_name):
            has_primary = "primaryInput" in node
            has_secondary = "secondaryInput" in node
            if has_primary and has_secondary:
                assert "operator" in node, (
                    f"Seed '{seed_name}' combine node '{node.get('id')}' "
                    f"missing operator"
                )
                assert node["operator"] in ("INTERSECT", "UNION", "MINUS"), (
                    f"Seed '{seed_name}' invalid operator: {node.get('operator')}"
                )
            if has_primary:
                _check_operators(node["primaryInput"], seed_name)
            if has_secondary:
                _check_operators(node["secondaryInput"], seed_name)

        for seed in SEEDS:
            _check_operators(seed.step_tree, seed.name)

    def test_all_provenance_notes_non_empty(self):
        for seed in SEEDS:
            assert seed.control_set.provenance_notes.strip(), (
                f"Seed '{seed.name}' has empty provenance_notes"
            )
