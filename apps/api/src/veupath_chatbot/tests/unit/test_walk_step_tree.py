"""Tests for walk_step_tree depth-first traversal."""

from veupath_chatbot.domain.strategy.ast import walk_step_tree
from veupath_chatbot.tests.fixtures.builders import (
    make_combine,
    make_leaf,
    make_transform,
)


class TestWalkStepTreeSingleLeaf:
    """Single leaf node returns a list with just that node."""

    def test_single_leaf(self) -> None:
        leaf = make_leaf("s1")
        result = walk_step_tree(leaf)
        assert len(result) == 1
        assert result[0].id == "s1"


class TestWalkStepTreeLinearChain:
    """Linear chain: search -> transform."""

    def test_search_then_transform(self) -> None:
        search = make_leaf("s1", name="GenesByGoTerm")
        transform = make_transform("t1", search)
        result = walk_step_tree(transform)
        assert len(result) == 2
        # primary_input (search) visited first, then transform
        assert result[0].id == "s1"
        assert result[1].id == "t1"

    def test_double_transform_chain(self) -> None:
        search = make_leaf("s1")
        t1 = make_transform("t1", search)
        t2 = make_transform("t2", t1, name="GenesByOrthologs")
        result = walk_step_tree(t2)
        assert len(result) == 3
        assert [s.id for s in result] == ["s1", "t1", "t2"]


class TestWalkStepTreeBinaryTree:
    """Binary tree: search + search -> combine."""

    def test_two_leaves_combined(self) -> None:
        left = make_leaf("s1")
        right = make_leaf("s2")
        combine = make_combine("c1", left, right)
        result = walk_step_tree(combine)
        assert len(result) == 3
        # primary_input first, then secondary_input, then combine
        assert result[0].id == "s1"
        assert result[1].id == "s2"
        assert result[2].id == "c1"

    def test_returns_actual_node_objects(self) -> None:
        left = make_leaf("s1")
        right = make_leaf("s2")
        combine = make_combine("c1", left, right)
        result = walk_step_tree(combine)
        assert result[0] is left
        assert result[1] is right
        assert result[2] is combine


class TestWalkStepTreeNestedCombines:
    """Nested combines: (s1 + s2) + s3."""

    def test_nested_combine(self) -> None:
        s1 = make_leaf("s1")
        s2 = make_leaf("s2")
        inner = make_combine("c_inner", s1, s2)
        s3 = make_leaf("s3")
        outer = make_combine("c_outer", inner, s3)
        result = walk_step_tree(outer)
        assert len(result) == 5
        # DFS: primary of outer -> primary of inner (s1) -> secondary of inner (s2)
        # -> inner combine -> secondary of outer (s3) -> outer combine
        assert [s.id for s in result] == ["s1", "s2", "c_inner", "s3", "c_outer"]

    def test_doubly_nested_combine(self) -> None:
        """(s1 + s2) + (s3 + s4)."""
        s1 = make_leaf("s1")
        s2 = make_leaf("s2")
        left = make_combine("c_left", s1, s2)
        s3 = make_leaf("s3")
        s4 = make_leaf("s4")
        right = make_combine("c_right", s3, s4)
        root = make_combine("c_root", left, right)
        result = walk_step_tree(root)
        assert len(result) == 7
        assert [s.id for s in result] == [
            "s1",
            "s2",
            "c_left",
            "s3",
            "s4",
            "c_right",
            "c_root",
        ]

    def test_walk_order_is_deterministic(self) -> None:
        """walk_step_tree always returns the same depth-first order."""
        s1 = make_leaf("s1")
        s2 = make_leaf("s2")
        inner = make_combine("c_inner", s1, s2)
        s3 = make_leaf("s3")
        root = make_combine("c_outer", inner, s3)

        order1 = [s.id for s in walk_step_tree(root)]
        order2 = [s.id for s in walk_step_tree(root)]
        assert order1 == order2
        assert order1 == ["s1", "s2", "c_inner", "s3", "c_outer"]
