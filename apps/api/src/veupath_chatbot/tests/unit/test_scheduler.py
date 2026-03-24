"""Unit tests for ai/orchestration/scheduler.py."""

import asyncio
from collections.abc import MutableSequence

import pytest

from veupath_chatbot.ai.orchestration.delegation import CompiledNode, CompiledTask
from veupath_chatbot.ai.orchestration.results import NodeResult, TaskResult
from veupath_chatbot.ai.orchestration.scheduler import (
    partition_task_results,
    run_nodes_with_dependencies,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_context(**_kwargs: object) -> None:
    """format_dependency_context stub that returns None."""
    return


def _make_task(
    node_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    task: str = "test task",
) -> CompiledTask:
    """Build a CompiledTask node for tests."""
    return CompiledTask(
        id=node_id,
        task=task,
        instructions="",
        context=None,
        depends_on=depends_on,
    )


def _make_run_node(
    order: MutableSequence[str] | None = None,
    delay: float = 0.0,
    results: dict[str, NodeResult] | None = None,
):
    """Build an async *run_node* callback.

    *order* — append node_id on each call so tests can assert execution order.
    *delay* — optional asyncio.sleep for concurrency tests.
    *results* — per-node result overrides; defaults to a success TaskResult.
    """

    async def run_node(
        node_id: str, node: CompiledNode, dep_context: str | None
    ) -> NodeResult:
        if order is not None:
            order.append(node_id)
        if delay:
            await asyncio.sleep(delay)
        if results and node_id in results:
            return results[node_id]
        return TaskResult(id=node_id, task="ok")

    return run_node


# ===================================================================
# run_nodes_with_dependencies — dependency ordering
# ===================================================================


class TestDependencyOrdering:
    """Nodes must execute in correct dependency order."""

    @pytest.mark.asyncio
    async def test_linear_chain_a_then_b(self) -> None:
        """A has no deps, B depends on A. A must run first."""
        order: list[str] = []
        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A"),
            "B": _make_task("B", depends_on=("A",)),
        }
        dependents = {"A": ["B"]}

        results, results_by_id = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=4,
            run_node=_make_run_node(order=order),
            format_dependency_context=_no_context,
        )

        assert order == ["A", "B"]
        assert len(results) == 2
        assert "A" in results_by_id
        assert "B" in results_by_id

    @pytest.mark.asyncio
    async def test_diamond_dependency(self) -> None:
        """Diamond: A -> B, A -> C, B+C -> D. D runs only after B and C."""
        order: list[str] = []
        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A"),
            "B": _make_task("B", depends_on=("A",)),
            "C": _make_task("C", depends_on=("A",)),
            "D": _make_task("D", depends_on=("B", "C")),
        }
        dependents = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}

        # Use max_concurrency=1 to make B and C sequential so order is deterministic
        results, _results_by_id = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=1,
            run_node=_make_run_node(order=order),
            format_dependency_context=_no_context,
        )

        assert order[0] == "A"
        assert order[-1] == "D"
        # B and C must both come between A and D
        middle = set(order[1:-1])
        assert middle == {"B", "C"}
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_no_deps_all_run(self) -> None:
        """Nodes with no dependencies all get scheduled."""
        order: list[str] = []
        nodes: dict[str, CompiledNode] = {
            "X": _make_task("X"),
            "Y": _make_task("Y"),
            "Z": _make_task("Z"),
        }
        dependents: dict[str, list[str]] = {}

        results, _ = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=10,
            run_node=_make_run_node(order=order),
            format_dependency_context=_no_context,
        )

        assert set(order) == {"X", "Y", "Z"}
        assert len(results) == 3


# ===================================================================
# run_nodes_with_dependencies — concurrency limiting
# ===================================================================


class TestConcurrencyLimiting:
    """Semaphore must limit how many nodes run in parallel."""

    @pytest.mark.asyncio
    async def test_max_concurrency_one_sequential(self) -> None:
        """max_concurrency=1: only one node executes at a time.

        We track *active* count and assert it never exceeds 1.
        """
        peak_concurrent = 0
        active = 0
        order: list[str] = []

        async def run_node(
            node_id: str, node: CompiledNode, dep_context: str | None
        ) -> NodeResult:
            nonlocal active, peak_concurrent
            active += 1
            peak_concurrent = max(peak_concurrent, active)
            order.append(node_id)
            await asyncio.sleep(0.02)
            active -= 1
            return TaskResult(id=node_id, task="ok")

        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A"),
            "B": _make_task("B"),
            "C": _make_task("C"),
        }
        dependents: dict[str, list[str]] = {}

        await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=1,
            run_node=run_node,
            format_dependency_context=_no_context,
        )

        assert peak_concurrent == 1
        assert len(order) == 3

    @pytest.mark.asyncio
    async def test_high_concurrency_all_start_immediately(self) -> None:
        """max_concurrency=10 with 3 independent nodes: all 3 start before any finishes."""
        started_count = 0
        all_started = asyncio.Event()

        async def run_node(
            node_id: str, node: CompiledNode, dep_context: str | None
        ) -> NodeResult:
            nonlocal started_count
            started_count += 1
            if started_count >= 3:
                all_started.set()
            # Wait until all three have started — proves concurrent start
            await asyncio.wait_for(all_started.wait(), timeout=2.0)
            return TaskResult(id=node_id, task="ok")

        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A"),
            "B": _make_task("B"),
            "C": _make_task("C"),
        }
        dependents: dict[str, list[str]] = {}

        results, _ = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=10,
            run_node=run_node,
            format_dependency_context=_no_context,
        )

        assert len(results) == 3
        assert started_count == 3


# ===================================================================
# run_nodes_with_dependencies — circular dependency detection
# ===================================================================


class TestCircularDependency:
    """Circular deps must be detected and produce unscheduled nodes."""

    @pytest.mark.asyncio
    async def test_mutual_circular_dependency(self) -> None:
        """A depends on B, B depends on A. Neither should be scheduled."""
        order: list[str] = []
        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A", depends_on=("B",)),
            "B": _make_task("B", depends_on=("A",)),
        }
        # Both are children of each other
        dependents = {"A": ["B"], "B": ["A"]}

        results, _ = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=4,
            run_node=_make_run_node(order=order),
            format_dependency_context=_no_context,
        )

        # Neither node should have been scheduled
        assert order == []
        # No results collected because no nodes ran
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_self_referencing_circular(self) -> None:
        """A depends on itself — should never be scheduled."""
        order: list[str] = []
        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A", depends_on=("A",)),
        }
        dependents = {"A": ["A"]}

        results, _ = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=4,
            run_node=_make_run_node(order=order),
            format_dependency_context=_no_context,
        )

        assert order == []
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_partial_circular_some_nodes_run(self) -> None:
        """A has no deps, B depends on C, C depends on B.

        A should run successfully. B and C should never be scheduled.
        """
        order: list[str] = []
        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A"),
            "B": _make_task("B", depends_on=("C",)),
            "C": _make_task("C", depends_on=("B",)),
        }
        dependents: dict[str, list[str]] = {"B": ["C"], "C": ["B"]}

        results, results_by_id = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=4,
            run_node=_make_run_node(order=order),
            format_dependency_context=_no_context,
        )

        assert order == ["A"]
        assert "A" in results_by_id
        # Only A ran successfully; B and C were never scheduled
        assert len(results) == 1


# ===================================================================
# run_nodes_with_dependencies — error propagation
# ===================================================================


class TestErrorPropagation:
    """Exceptions and error dicts from run_node are handled correctly."""

    @pytest.mark.asyncio
    async def test_run_node_raises_propagates(self) -> None:
        """If run_node raises, the exception propagates from .result()."""

        async def failing_run_node(
            node_id: str, node: CompiledNode, dep_context: str | None
        ) -> NodeResult:
            msg = f"boom from {node_id}"
            raise ValueError(msg)

        nodes: dict[str, CompiledNode] = {"A": _make_task("A")}
        dependents: dict[str, list[str]] = {}

        with pytest.raises(ValueError, match="boom from A"):
            await run_nodes_with_dependencies(
                nodes_by_id=nodes,
                dependents=dependents,
                max_concurrency=4,
                run_node=failing_run_node,
                format_dependency_context=_no_context,
            )

    @pytest.mark.asyncio
    async def test_run_node_returns_error_result_collected(self) -> None:
        """If run_node returns a TaskResult with error info, it is still collected."""
        error_result = TaskResult(
            id="A",
            task="will-error",
            ok=False,
            error="oops",
        )

        results, results_by_id = await run_nodes_with_dependencies(
            nodes_by_id={"A": _make_task("A", task="will-error")},
            dependents={},
            max_concurrency=4,
            run_node=_make_run_node(results={"A": error_result}),
            format_dependency_context=_no_context,
        )

        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].error == "oops"
        assert "A" in results_by_id


# ===================================================================
# run_nodes_with_dependencies — format_dependency_context
# ===================================================================


class TestFormatDependencyContext:
    """The format_dependency_context callback is invoked correctly."""

    @pytest.mark.asyncio
    async def test_context_passed_to_run_node(self) -> None:
        """format_dependency_context return value is forwarded to run_node."""
        received_contexts: dict[str, str | None] = {}

        def format_ctx(
            *, task_id: str, tasks_by_id: object, results_by_id: object
        ) -> str | None:
            if task_id == "B":
                return "context-from-A"
            return None

        async def capturing_run_node(
            node_id: str, node: CompiledNode, dep_context: str | None
        ) -> NodeResult:
            received_contexts[node_id] = dep_context
            return TaskResult(id=node_id, task="ok")

        nodes: dict[str, CompiledNode] = {
            "A": _make_task("A"),
            "B": _make_task("B", depends_on=("A",)),
        }
        dependents = {"A": ["B"]}

        await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents=dependents,
            max_concurrency=4,
            run_node=capturing_run_node,
            format_dependency_context=format_ctx,
        )

        assert received_contexts["A"] is None
        assert received_contexts["B"] == "context-from-A"


# ===================================================================
# run_nodes_with_dependencies — results_by_id pre-populated
# ===================================================================


class TestResultsByIdPrePopulated:
    """Callers can pass an existing results_by_id dict."""

    @pytest.mark.asyncio
    async def test_existing_results_preserved(self) -> None:
        existing: dict[str, NodeResult] = {
            "prior": TaskResult(id="prior", task="prior task"),
        }
        nodes: dict[str, CompiledNode] = {"A": _make_task("A")}

        _, results_by_id = await run_nodes_with_dependencies(
            nodes_by_id=nodes,
            dependents={},
            max_concurrency=4,
            run_node=_make_run_node(),
            format_dependency_context=_no_context,
            results_by_id=existing,
        )

        assert "prior" in results_by_id
        assert "A" in results_by_id


# ===================================================================
# partition_task_results
# ===================================================================


class TestPartitionTaskResults:
    """partition_task_results splits results into validated/rejected."""

    def test_results_with_steps_go_to_validated(self) -> None:
        results = [
            {
                "id": "t1",
                "task": "find genes",
                "steps": [{"search": "GenesByTextSearch"}],
                "notes": "ok",
            }
        ]
        validated, rejected = partition_task_results(results)

        assert len(validated) == 1
        assert len(rejected) == 0
        assert validated[0]["id"] == "t1"
        assert validated[0]["task"] == "find genes"
        assert validated[0]["steps"] == [{"search": "GenesByTextSearch"}]
        assert validated[0]["notes"] == "ok"

    def test_results_with_empty_steps_go_to_rejected(self) -> None:
        results = [{"id": "t2", "task": "bad task", "steps": [], "notes": "failed"}]
        validated, rejected = partition_task_results(results)

        assert len(validated) == 1
        assert len(rejected) == 1

        # Validated gets a skeleton entry with empty steps
        assert validated[0]["id"] == "t2"
        assert validated[0]["task"] == "bad task"
        assert validated[0]["steps"] == []
        assert validated[0]["notes"] == "failed"

        # Rejected has the NO_STEPS_CREATED error
        assert rejected[0]["code"] == "NO_STEPS_CREATED"
        assert rejected[0]["id"] == "t2"
        assert rejected[0]["task"] == "bad task"
        assert rejected[0]["ok"] is False

    def test_results_without_steps_key_go_to_rejected(self) -> None:
        results = [{"id": "t3", "task": "no steps field"}]
        validated, rejected = partition_task_results(results)

        assert len(validated) == 1
        assert len(rejected) == 1
        assert rejected[0]["code"] == "NO_STEPS_CREATED"
        assert rejected[0]["id"] == "t3"

    def test_non_dict_items_skipped(self) -> None:
        results = ["not-a-dict", 42, None, True]
        validated, rejected = partition_task_results(results)

        assert len(validated) == 0
        assert len(rejected) == 0

    def test_mixed_results(self) -> None:
        results = [
            {
                "id": "good",
                "task": "search",
                "steps": [{"s": 1}],
                "notes": "fine",
            },
            {
                "id": "bad",
                "task": "empty",
                "steps": [],
                "notes": None,
            },
            "skip-me",
            {
                "id": "also-bad",
                "task": "missing steps",
            },
        ]
        validated, rejected = partition_task_results(results)

        assert len(validated) == 3  # good + bad skeleton + also-bad skeleton
        assert len(rejected) == 2  # bad + also-bad

        validated_ids = [v["id"] for v in validated if isinstance(v, dict)]
        assert validated_ids == ["good", "bad", "also-bad"]

        rejected_ids = [r["id"] for r in rejected if isinstance(r, dict)]
        assert rejected_ids == ["bad", "also-bad"]

    def test_preserves_id_task_notes_fields(self) -> None:
        results = [
            {
                "id": "x1",
                "task": "my task",
                "steps": [{"search": "A"}],
                "notes": "some notes",
                "extra_field": "ignored",
            }
        ]
        validated, _ = partition_task_results(results)

        assert len(validated) == 1
        entry = validated[0]
        assert isinstance(entry, dict)
        # Only id, task, steps, notes are preserved
        assert set(entry.keys()) == {"id", "task", "steps", "notes"}

    def test_empty_results(self) -> None:
        validated, rejected = partition_task_results([])
        assert validated == []
        assert rejected == []
