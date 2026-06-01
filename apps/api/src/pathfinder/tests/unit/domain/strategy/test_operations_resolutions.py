from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.operations import DeleteResolution
from pathfinder.domain.strategy.operations.resolutions import (
    compute_delete_choices,
    is_ambiguous_delete,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph


def _graph_from_root(root: StrategyStepNode, name: str = "g") -> StrategyGraph:
    g = StrategyGraph(graph_id="g1", name=name, site_id="plasmodb")

    def visit(n: StrategyStepNode) -> None:
        g.steps[n.id] = n
        if n.primary_input is not None:
            visit(n.primary_input)
        if n.secondary_input is not None:
            visit(n.secondary_input)

    visit(root)
    g.recompute_roots()
    return g


def _leaf(id_: str) -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name="geneById")


class TestComputeDeleteChoices:
    def test_sole_leaf_only_delete_strategy(self) -> None:
        g = _graph_from_root(_leaf("a"))
        choices = compute_delete_choices(g, "a")
        assert [c.resolution for c in choices] == [DeleteResolution.DELETE_STRATEGY]
        assert choices[0].will_delete == ["a"]
        assert choices[0].is_default

    def test_leaf_of_root_combine(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = StrategyStepNode(
            id="c",
            search_name="__combine__",
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.INTERSECT,
        )
        g = _graph_from_root(c)
        choices = compute_delete_choices(g, "a")
        assert {c.resolution for c in choices} == {
            DeleteResolution.COLLAPSE_COMBINE,
            DeleteResolution.DELETE_SUBTREE,
        }
        default = next(c for c in choices if c.is_default)
        assert default.resolution == DeleteResolution.COLLAPSE_COMBINE
        collapse = next(
            c for c in choices if c.resolution == DeleteResolution.COLLAPSE_COMBINE
        )
        assert sorted(collapse.will_delete) == ["a", "c"]

    def test_root_combine_promote_or_delete_strategy(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = StrategyStepNode(
            id="c",
            search_name="__combine__",
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.INTERSECT,
        )
        g = _graph_from_root(c)
        choices = compute_delete_choices(g, "c")
        assert {c.resolution for c in choices} == {
            DeleteResolution.PROMOTE_PRIMARY,
            DeleteResolution.DELETE_STRATEGY,
        }
        promote = next(
            c for c in choices if c.resolution == DeleteResolution.PROMOTE_PRIMARY
        )
        assert sorted(promote.will_delete) == ["b", "c"]

    def test_transform_in_middle(self) -> None:
        a = _leaf("a")
        t = StrategyStepNode(
            id="t",
            search_name="orthologs",
            primary_input=a,
        )
        g = _graph_from_root(t)
        choices = compute_delete_choices(g, "t")
        assert [c.resolution for c in choices] == [DeleteResolution.COLLAPSE_COMBINE]
        assert choices[0].will_delete == ["t"]

    def test_step_whose_parent_is_transform_cascades(self) -> None:
        a = _leaf("a")
        t = StrategyStepNode(
            id="t",
            search_name="orthologs",
            primary_input=a,
        )
        g = _graph_from_root(t)
        choices = compute_delete_choices(g, "a")
        assert [c.resolution for c in choices] == [DeleteResolution.DELETE_SUBTREE]
        assert sorted(choices[0].will_delete) == ["a", "t"]

    def test_unknown_step_returns_empty(self) -> None:
        g = _graph_from_root(_leaf("a"))
        assert compute_delete_choices(g, "missing") == []


class TestIsAmbiguousDelete:
    def test_true_when_multiple_choices(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = StrategyStepNode(
            id="c",
            search_name="__combine__",
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.INTERSECT,
        )
        g = _graph_from_root(c)
        assert is_ambiguous_delete(g, "a") is True

    def test_false_when_single_choice(self) -> None:
        g = _graph_from_root(_leaf("a"))
        assert is_ambiguous_delete(g, "a") is False
