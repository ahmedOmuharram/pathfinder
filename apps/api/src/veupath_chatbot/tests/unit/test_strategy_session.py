"""Unit tests for StrategyGraph session operations."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode, walk_step_tree
from veupath_chatbot.domain.strategy.session import (
    StrategyGraph,
    StrategySession,
)
from veupath_chatbot.tests.fixtures.builders import make_combine, make_leaf


def _make_leaf(step_id: str, search_name: str = "GenesByTextSearch") -> PlanStepNode:
    return make_leaf(step_id, name=search_name, parameters={"text_expression": step_id})


def _make_combine(
    step_id: str,
    left: PlanStepNode,
    right: PlanStepNode,
) -> PlanStepNode:
    return make_combine(step_id, left, right)


def _build_graph_with_steps(n_leaves: int = 2) -> StrategyGraph:
    """Build a StrategyGraph with a simple combine from leaf steps."""
    graph = StrategyGraph("g1", "Test", "plasmodb")
    graph.record_type = "gene"
    leaves = [_make_leaf(f"step{i + 1}") for i in range(n_leaves)]
    root = _make_combine("step_combine", leaves[0], leaves[1])
    all_steps = walk_step_tree(root)
    for step in all_steps:
        graph.steps[step.id] = step
    graph.recompute_roots()
    graph.last_step_id = root.id
    return graph


class TestAddStep:
    def test_adds_step_to_graph(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        step = _make_leaf("s1")
        graph.add_step(step)
        assert "s1" in graph.steps
        assert graph.steps["s1"] is step

    def test_step_becomes_root(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.add_step(_make_leaf("s1"))
        assert "s1" in graph.roots

    def test_combine_removes_input_roots(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        left = _make_leaf("s1")
        right = _make_leaf("s2")
        graph.add_step(left)
        graph.add_step(right)
        assert graph.roots == {"s1", "s2"}
        combine = _make_combine("c1", left, right)
        graph.add_step(combine)
        assert graph.roots == {"c1"}

    def test_sets_last_step_id(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.add_step(_make_leaf("s1"))
        assert graph.last_step_id == "s1"
        graph.add_step(_make_leaf("s2"))
        assert graph.last_step_id == "s2"


class TestGetStep:
    def test_returns_step(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        step = _make_leaf("s1")
        graph.add_step(step)
        assert graph.get_step("s1") is step

    def test_returns_none_for_missing(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        assert graph.get_step("nope") is None


class TestRecomputeRoots:
    def test_finds_single_root(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        left = _make_leaf("s1")
        right = _make_leaf("s2")
        combine = _make_combine("c1", left, right)
        graph.steps = {"s1": left, "s2": right, "c1": combine}
        graph.recompute_roots()
        assert graph.roots == {"c1"}

    def test_multiple_disconnected_roots(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.steps = {"s1": _make_leaf("s1"), "s2": _make_leaf("s2")}
        graph.recompute_roots()
        assert graph.roots == {"s1", "s2"}

    def test_empty_graph(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.recompute_roots()
        assert graph.roots == set()


class TestToPlan:
    def test_produces_plan_for_single_root(self) -> None:
        graph = _build_graph_with_steps()
        plan = graph.to_plan()
        assert plan["recordType"] == "gene"
        assert plan["name"] == "Test"
        assert "root" in plan

    def test_returns_empty_dict_when_no_root(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        plan = graph.to_plan()
        assert plan == {}

    def test_returns_empty_when_multiple_roots(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.record_type = "gene"
        graph.add_step(_make_leaf("s1"))
        graph.add_step(_make_leaf("s2"))
        # Two roots, no root_step_id specified -> empty
        plan = graph.to_plan()
        assert plan == {}

    def test_explicit_root_step_id(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.record_type = "gene"
        s1 = _make_leaf("s1")
        graph.add_step(s1)
        graph.add_step(_make_leaf("s2"))
        plan = graph.to_plan(root_step_id="s1")
        assert plan["root"]["searchName"] == "GenesByTextSearch"

    def test_includes_description_when_set(self) -> None:
        graph = _build_graph_with_steps()
        graph.description = "A test strategy"
        plan = graph.to_plan()
        assert plan["description"] == "A test strategy"

    def test_excludes_description_when_none(self) -> None:
        graph = _build_graph_with_steps()
        plan = graph.to_plan()
        assert "description" not in plan

    def test_includes_step_counts_when_present(self) -> None:
        graph = _build_graph_with_steps()
        graph.step_counts = {"step1": 10, "step2": 20}
        plan = graph.to_plan()
        assert plan["stepCounts"] == {"step1": 10, "step2": 20}

    def test_filters_none_step_counts(self) -> None:
        graph = _build_graph_with_steps()
        graph.step_counts = {"step1": 10, "step2": None}
        plan = graph.to_plan()
        assert plan["stepCounts"] == {"step1": 10}

    def test_includes_wdk_step_ids_when_present(self) -> None:
        graph = _build_graph_with_steps()
        graph.wdk_step_ids = {"step1": 100, "step2": 200}
        plan = graph.to_plan()
        assert plan["wdkStepIds"] == {"step1": 100, "step2": 200}


class TestStrategySessionCreateGraph:
    def test_creates_new_graph(self) -> None:
        session = StrategySession("plasmodb")
        graph = session.create_graph("My Strategy", graph_id="g1")
        assert graph.id == "g1"
        assert graph.name == "My Strategy"
        assert session.graph is graph

    def test_returns_existing_graph(self) -> None:
        session = StrategySession("plasmodb")
        g1 = session.create_graph("First")
        g2 = session.create_graph("Second")
        assert g1 is g2
        assert g1.name == "Second"

    def test_auto_generates_id(self) -> None:
        session = StrategySession("plasmodb")
        graph = session.create_graph("Test")
        assert graph.id  # not empty


class TestStrategySessionAddGraph:
    def test_registers_graph(self) -> None:
        session = StrategySession("plasmodb")
        graph = StrategyGraph("g1", "Test", "plasmodb")
        session.add_graph(graph)
        assert session.graph is graph

    def test_ignores_different_graph_when_one_exists(self) -> None:
        session = StrategySession("plasmodb")
        g1 = StrategyGraph("g1", "First", "plasmodb")
        g2 = StrategyGraph("g2", "Second", "plasmodb")
        session.add_graph(g1)
        session.add_graph(g2)
        assert session.graph is g1

    def test_allows_same_graph_id(self) -> None:
        session = StrategySession("plasmodb")
        g1 = StrategyGraph("g1", "First", "plasmodb")
        session.add_graph(g1)
        g1_again = StrategyGraph("g1", "Updated", "plasmodb")
        session.add_graph(g1_again)
        assert session.graph is g1_again


class TestStrategySessionGetGraph:
    def test_returns_active_graph_for_none(self) -> None:
        session = StrategySession("plasmodb")
        graph = session.create_graph("Test", graph_id="g1")
        assert session.get_graph(None) is graph

    def test_returns_matching_graph(self) -> None:
        session = StrategySession("plasmodb")
        graph = session.create_graph("Test", graph_id="g1")
        assert session.get_graph("g1") is graph

    def test_returns_none_for_wrong_id(self) -> None:
        session = StrategySession("plasmodb")
        session.create_graph("Test", graph_id="g1")
        assert session.get_graph("g2") is None

    def test_returns_none_when_empty(self) -> None:
        session = StrategySession("plasmodb")
        assert session.get_graph(None) is None


class TestSaveHistory:
    def test_saves_when_graph_has_root(self) -> None:
        graph = _build_graph_with_steps()
        graph.save_history("test")
        assert len(graph.history) == 1
        assert graph.history[0]["description"] == "test"
        assert "plan" in graph.history[0]

    def test_noop_when_no_steps(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.save_history("test")
        assert len(graph.history) == 0

    def test_plan_contains_root(self) -> None:
        graph = _build_graph_with_steps()
        graph.save_history("test")
        plan = graph.history[0]["plan"]
        assert "root" in plan
        assert plan["recordType"] == "gene"


class TestUndoRestoresFullGraphState:
    """Undo must restore steps, roots, and last_step_id."""

    def test_undo_restores_steps(self) -> None:
        graph = _build_graph_with_steps()
        assert len(graph.steps) == 3
        graph.save_history("initial 3-step strategy")

        # Add a 4th step and create a new combine on top
        extra = _make_leaf("step_extra")
        graph.add_step(extra)
        assert len(graph.steps) == 4, "Precondition: 4 steps after add"

        # Build new root combining old root + new step
        old_root_id = next(iter(graph.roots - {"step_extra"}))
        old_root = graph.steps[old_root_id]
        new_root = _make_combine("step_new_root", old_root, extra)
        all_steps = walk_step_tree(new_root)
        graph.steps = {s.id: s for s in all_steps}
        graph.recompute_roots()
        graph.last_step_id = new_root.id
        graph.save_history("added 4th step")

        assert len(graph.steps) == 5, "Precondition: 5 steps after combine"

        # Undo
        result = graph.undo()
        assert result is True

        # After undo, steps must reflect the 3-step strategy
        assert len(graph.steps) == 3, (
            f"Expected 3 steps after undo, got {len(graph.steps)}: "
            f"{list(graph.steps.keys())}"
        )

    def test_undo_restores_roots(self) -> None:
        graph = _build_graph_with_steps()
        graph.save_history("initial")
        original_roots = set(graph.roots)

        # Modify graph
        extra = _make_leaf("step_extra")
        graph.add_step(extra)
        old_root_id = next(iter(graph.roots - {"step_extra"}))
        old_root = graph.steps[old_root_id]
        new_root = _make_combine("step_new_root", old_root, extra)
        all_steps = walk_step_tree(new_root)
        graph.steps = {s.id: s for s in all_steps}
        graph.recompute_roots()
        graph.last_step_id = new_root.id
        graph.save_history("modified")

        graph.undo()
        assert graph.roots == original_roots, (
            f"Expected roots {original_roots}, got {graph.roots}"
        )

    def test_undo_restores_last_step_id(self) -> None:
        graph = _build_graph_with_steps()
        original_last = graph.last_step_id
        graph.save_history("initial")

        extra = _make_leaf("step_extra")
        graph.add_step(extra)
        old_root_id = next(iter(graph.roots - {"step_extra"}))
        old_root = graph.steps[old_root_id]
        new_root = _make_combine("step_new_root", old_root, extra)
        all_steps = walk_step_tree(new_root)
        graph.steps = {s.id: s for s in all_steps}
        graph.recompute_roots()
        graph.last_step_id = new_root.id
        graph.save_history("modified")

        assert graph.last_step_id == "step_new_root"
        graph.undo()
        assert graph.last_step_id == original_last, (
            f"Expected last_step_id={original_last}, got {graph.last_step_id}"
        )

    def test_undo_with_insufficient_history_returns_false(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        assert graph.undo() is False

        graph.record_type = "gene"
        s = _make_leaf("s1")
        graph.add_step(s)
        graph.save_history("only one")
        assert graph.undo() is False

    def test_undo_old_strategy_format_fails_gracefully(self) -> None:
        """Old-format history entries are no longer supported (StrategyAST removed).

        Undo returns False when encountering old-format entries.
        """
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.record_type = "gene"
        s1 = _make_leaf("s1")
        graph.add_step(s1)

        # Manually inject old-format history entries
        old_entry = {
            "description": "old format",
            "strategy": {
                "recordType": "gene",
                "root": {
                    "searchName": "GenesByTextSearch",
                    "parameters": {"text_expression": "s1"},
                    "id": "s1",
                },
            },
        }
        graph.history.append(old_entry)
        graph.history.append(old_entry)  # need >= 2 for undo

        result = graph.undo()
        assert result is False
