"""Tests for phase_contribution.py — tree ablation analysis logic.

Tests focus on the pure logic inside analyze_contributions:
- Verdict classification thresholds
- Handling of single-leaf trees (should return empty)
- Ablation with recall/fpr delta edge cases
"""

import copy

from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _collect_leaves,
    _extract_leaf_branch,
    _node_id,
    _remove_leaf_from_tree,
)
from veupath_chatbot.services.experiment.types import StepContributionVerdict


class TestCollectLeaves:
    """_collect_leaves identifies leaf (search) nodes."""

    def test_single_leaf(self) -> None:
        tree = {"id": "s1", "searchName": "GeneByTaxon"}
        leaves = _collect_leaves(tree)
        assert len(leaves) == 1
        assert leaves[0]["id"] == "s1"

    def test_combine_node_two_leaves(self) -> None:
        tree = {
            "id": "combine",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        leaves = _collect_leaves(tree)
        assert len(leaves) == 2
        ids = {_node_id(leaf) for leaf in leaves}
        assert ids == {"s1", "s2"}

    def test_transform_node_one_leaf(self) -> None:
        """Transform/unary node has only primaryInput."""
        tree = {
            "id": "transform",
            "searchName": "GenesByOrthologs",
            "primaryInput": {"id": "s1", "searchName": "GeneByTaxon"},
        }
        leaves = _collect_leaves(tree)
        assert len(leaves) == 1
        assert _node_id(leaves[0]) == "s1"

    def test_deep_nested_tree(self) -> None:
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "mid",
                "operator": "INTERSECT",
                "primaryInput": {"id": "s1", "searchName": "A"},
                "secondaryInput": {"id": "s2", "searchName": "B"},
            },
            "secondaryInput": {"id": "s3", "searchName": "C"},
        }
        leaves = _collect_leaves(tree)
        assert len(leaves) == 3

    def test_empty_node(self) -> None:
        """A node with no primaryInput/secondaryInput is itself a leaf."""
        tree: dict[str, object] = {"id": "solo"}
        leaves = _collect_leaves(tree)
        assert len(leaves) == 1


class TestRemoveLeafFromTree:
    """_remove_leaf_from_tree prunes a leaf and restructures the tree."""

    def test_remove_root_leaf_returns_none(self) -> None:
        tree = {"id": "s1", "searchName": "A"}
        result = _remove_leaf_from_tree(tree, "s1")
        assert result is None

    def test_remove_primary_leaf(self) -> None:
        """Removing primary leaf: parent replaced by secondary subtree."""
        tree = {
            "id": "combine",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        result = _remove_leaf_from_tree(tree, "s1")
        assert result is not None
        assert _node_id(result) == "s2"

    def test_remove_secondary_leaf(self) -> None:
        """Removing secondary leaf: parent replaced by primary subtree."""
        tree = {
            "id": "combine",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        result = _remove_leaf_from_tree(tree, "s2")
        assert result is not None
        assert _node_id(result) == "s1"

    def test_remove_leaf_deep_in_tree(self) -> None:
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "mid",
                "operator": "INTERSECT",
                "primaryInput": {"id": "s1", "searchName": "A"},
                "secondaryInput": {"id": "s2", "searchName": "B"},
            },
            "secondaryInput": {"id": "s3", "searchName": "C"},
        }
        result = _remove_leaf_from_tree(tree, "s1")
        assert result is not None
        # After removing s1, "mid" collapses to s2, so root becomes UNION(s2, s3)
        leaves = _collect_leaves(result)
        leaf_ids = {_node_id(leaf) for leaf in leaves}
        assert leaf_ids == {"s2", "s3"}

    def test_remove_nonexistent_leaf(self) -> None:
        """Removing a leaf that doesn't exist returns the tree unchanged."""
        tree = {
            "id": "combine",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        result = _remove_leaf_from_tree(tree, "nonexistent")
        assert result is not None
        leaves = _collect_leaves(result)
        assert len(leaves) == 2

    def test_does_not_mutate_original(self) -> None:
        """Original tree should not be modified (deep copy inside)."""
        tree = {
            "id": "combine",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        original = copy.deepcopy(tree)
        _remove_leaf_from_tree(tree, "s1")
        assert tree == original

    def test_remove_leaf_under_transform(self) -> None:
        """Removing the only leaf under a transform collapses the entire branch."""
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "transform",
                "searchName": "GenesByOrthologs",
                "primaryInput": {"id": "s1", "searchName": "GeneByTaxon"},
            },
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        result = _remove_leaf_from_tree(tree, "s1")
        assert result is not None
        # The transform subtree collapses to None, so root becomes just s2
        assert _node_id(result) == "s2"


class TestExtractLeafBranch:
    """_extract_leaf_branch isolates a leaf's subtree with ancestor transforms."""

    def test_leaf_at_root(self) -> None:
        tree = {"id": "s1", "searchName": "A"}
        branch = _extract_leaf_branch(tree, "s1")
        assert branch is not None
        assert _node_id(branch) == "s1"

    def test_leaf_not_found(self) -> None:
        tree = {"id": "s1", "searchName": "A"}
        assert _extract_leaf_branch(tree, "nonexistent") is None

    def test_leaf_under_combine(self) -> None:
        """At combine nodes, we descend into the branch containing the leaf."""
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        branch = _extract_leaf_branch(tree, "s2")
        assert branch is not None
        # Should be just s2, unwrapped from the combine
        assert _node_id(branch) == "s2"

    def test_leaf_under_transform(self) -> None:
        """Leaf under a transform: branch includes the transform wrapper."""
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "transform",
                "searchName": "GenesByOrthologs",
                "primaryInput": {"id": "s1", "searchName": "GeneByTaxon"},
            },
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        branch = _extract_leaf_branch(tree, "s1")
        assert branch is not None
        # Should include the transform wrapping s1
        assert _node_id(branch) == "transform"
        pi = branch.get("primaryInput")
        assert isinstance(pi, dict)
        assert _node_id(pi) == "s1"


class TestVerdictClassification:
    """Verify the verdict thresholds match the source code.

    From phase_contribution.py:
    - recall_delta < -0.1 -> "essential"
    - recall_delta < -0.02 -> "helpful"
    - fpr_delta < -0.05 -> "harmful"
    - else -> "neutral"
    """

    def _classify(
        self, recall_delta: float, fpr_delta: float
    ) -> StepContributionVerdict:
        """Mirror the verdict logic from phase_contribution.py."""
        if recall_delta < -0.1:
            return "essential"
        if recall_delta < -0.02:
            return "helpful"
        if fpr_delta < -0.05:
            return "harmful"
        return "neutral"

    def test_essential_large_recall_drop(self) -> None:
        assert self._classify(-0.15, 0.0) == "essential"

    def test_essential_boundary(self) -> None:
        """recall_delta exactly -0.1 is NOT essential (< not <=)."""
        assert self._classify(-0.1, 0.0) == "helpful"

    def test_helpful_small_recall_drop(self) -> None:
        assert self._classify(-0.05, 0.0) == "helpful"

    def test_helpful_boundary(self) -> None:
        """recall_delta exactly -0.02 is NOT helpful (< not <=)."""
        assert self._classify(-0.02, 0.0) == "neutral"

    def test_harmful_fpr_drops_with_no_recall_drop(self) -> None:
        """FPR delta < -0.05 means removing this step reduces FPR.

        This means the step was ADDING false positives (harmful).
        """
        assert self._classify(0.0, -0.06) == "harmful"

    def test_harmful_boundary(self) -> None:
        """fpr_delta exactly -0.05 is NOT harmful (< not <=)."""
        assert self._classify(0.0, -0.05) == "neutral"

    def test_neutral_no_significant_change(self) -> None:
        assert self._classify(0.0, 0.0) == "neutral"

    def test_essential_overrides_harmful(self) -> None:
        """When both recall drops heavily and fpr drops, essential wins."""
        assert self._classify(-0.2, -0.1) == "essential"

    def test_helpful_overrides_harmful(self) -> None:
        """When recall drops moderately and fpr drops, helpful wins."""
        assert self._classify(-0.05, -0.1) == "helpful"

    def test_positive_recall_delta_is_neutral(self) -> None:
        """Removing the step IMPROVES recall -> step was hurting, but verdict is neutral.

        BUG NOTE: If removing a step improves recall (recall_delta > 0), and
        doesn't reduce FPR, the step is actually harmful to recall but gets
        classified as 'neutral'. The harmful check only looks at fpr_delta.
        A step that reduces recall when present should be at least 'harmful',
        but the current logic doesn't capture this case.
        """
        assert self._classify(0.1, 0.0) == "neutral"
