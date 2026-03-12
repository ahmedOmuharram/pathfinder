"""Extended tests for seed integrity — control sizes, step tree structure, gene IDs."""

from veupath_chatbot.services.experiment.seed.seeds import get_all_seeds

SEEDS = get_all_seeds()


# ---------------------------------------------------------------------------
# Seed positive/negative control sizes
# ---------------------------------------------------------------------------


class TestSeedControlSizes:
    def test_all_seeds_have_at_least_5_positives(self):
        for seed in SEEDS:
            assert len(seed.control_set.positive_ids) >= 5, (
                f"Seed '{seed.name}' has only {len(seed.control_set.positive_ids)} positives"
            )

    def test_all_seeds_have_at_least_5_negatives(self):
        for seed in SEEDS:
            assert len(seed.control_set.negative_ids) >= 5, (
                f"Seed '{seed.name}' has only {len(seed.control_set.negative_ids)} negatives"
            )


# ---------------------------------------------------------------------------
# Seed step tree IDs are unique within each tree
# ---------------------------------------------------------------------------


class TestStepTreeIdUniqueness:
    def _collect_ids(self, node: dict) -> list[str]:
        ids = []
        node_id = node.get("id")
        if node_id:
            ids.append(node_id)
        if "primaryInput" in node:
            ids.extend(self._collect_ids(node["primaryInput"]))
        if "secondaryInput" in node:
            ids.extend(self._collect_ids(node["secondaryInput"]))
        return ids

    def test_all_seed_step_ids_unique_within_tree(self):
        for seed in SEEDS:
            ids = self._collect_ids(seed.step_tree)
            assert len(ids) == len(set(ids)), (
                f"Seed '{seed.name}' has duplicate step IDs: "
                f"{[i for i in ids if ids.count(i) > 1]}"
            )


# ---------------------------------------------------------------------------
# Gene ID format: no whitespace, all strings
# ---------------------------------------------------------------------------


class TestGeneIdFormats:
    def test_all_control_ids_are_strings(self):
        for seed in SEEDS:
            for gid in seed.control_set.positive_ids + seed.control_set.negative_ids:
                assert isinstance(gid, str), (
                    f"Seed '{seed.name}' has non-string gene ID: {gid!r}"
                )
                assert gid.strip() == gid, (
                    f"Seed '{seed.name}' has whitespace-padded ID: {gid!r}"
                )
                assert len(gid) > 0, f"Seed '{seed.name}' has empty gene ID"
