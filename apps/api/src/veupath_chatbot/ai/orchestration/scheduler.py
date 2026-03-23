"""Run delegation graph nodes respecting dependency ordering."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from veupath_chatbot.ai.orchestration.delegation import CompiledNode
from veupath_chatbot.ai.orchestration.results import NodeResult
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


@dataclass
class SchedulerState:
    """Shared state for the dependency-aware node scheduler."""

    nodes_by_id: dict[str, CompiledNode]
    format_dependency_context: Callable[..., str | None]
    results_by_id: dict[str, NodeResult]
    guarded_run: Callable[..., Coroutine[Any, Any, NodeResult]]
    max_concurrency: int


def _compute_remaining_deps(
    nodes_by_id: dict[str, CompiledNode],
    node_ids: set[str],
) -> dict[str, set[str]]:
    """Compute initial remaining dependencies for each node."""
    return {
        node_id: {dep for dep in node.depends_on if dep in node_ids}
        for node_id, node in nodes_by_id.items()
    }


async def _schedule_and_run(
    *,
    state: SchedulerState,
    dependents: dict[str, list[str]],
    remaining_deps: dict[str, set[str]],
) -> tuple[list[NodeResult], set[str]]:
    """Run nodes with concurrency control and dependency tracking."""
    ready = [node_id for node_id, deps in remaining_deps.items() if not deps]
    running: dict[asyncio.Task[NodeResult], str] = {}
    results: list[NodeResult] = []
    all_scheduled: set[str] = set()

    while ready or running:
        _launch_ready_nodes(
            ready=ready,
            running=running,
            all_scheduled=all_scheduled,
            state=state,
        )

        if not running:
            break

        done, _ = await asyncio.wait(
            running.keys(), return_when=asyncio.FIRST_COMPLETED
        )
        for finished in done:
            finished_id = running.pop(finished)
            result = finished.result()
            results.append(result)
            state.results_by_id[finished_id] = result
            for child in dependents.get(finished_id, []):
                remaining_deps[child].discard(finished_id)
                if not remaining_deps[child]:
                    ready.append(child)

    return results, all_scheduled


def _launch_ready_nodes(
    *,
    ready: list[str],
    running: dict[asyncio.Task[NodeResult], str],
    all_scheduled: set[str],
    state: SchedulerState,
) -> None:
    """Launch as many ready nodes as concurrency allows."""
    while ready and len(running) < max(1, int(state.max_concurrency)):
        node_id = ready.pop()
        all_scheduled.add(node_id)
        node = state.nodes_by_id[node_id]
        dependency_context = state.format_dependency_context(
            task_id=node_id,
            tasks_by_id=state.nodes_by_id,
            results_by_id=state.results_by_id,
        )
        running_task: asyncio.Task[NodeResult] = asyncio.create_task(
            state.guarded_run(node_id, node, dependency_context)
        )
        running[running_task] = node_id


async def run_nodes_with_dependencies(
    *,
    nodes_by_id: dict[str, CompiledNode],
    dependents: dict[str, list[str]],
    max_concurrency: int,
    run_node: Callable[[str, CompiledNode, str | None], Awaitable[NodeResult]],
    format_dependency_context: Callable[..., str | None],
    results_by_id: dict[str, NodeResult] | None = None,
) -> tuple[list[NodeResult], dict[str, NodeResult]]:
    """Execute nodes concurrently while honoring their depends_on edges."""
    node_ids = set(nodes_by_id.keys())
    remaining_deps = _compute_remaining_deps(nodes_by_id, node_ids)
    if results_by_id is None:
        results_by_id = {}

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def guarded_run(
        node_id: str, node: CompiledNode, dependency_context: str | None
    ) -> NodeResult:
        async with semaphore:
            return await run_node(node_id, node, dependency_context)

    state = SchedulerState(
        nodes_by_id=nodes_by_id,
        format_dependency_context=format_dependency_context,
        results_by_id=results_by_id,
        guarded_run=guarded_run,
        max_concurrency=max_concurrency,
    )

    results, all_scheduled = await _schedule_and_run(
        state=state,
        dependents=dependents,
        remaining_deps=remaining_deps,
    )

    # Report any nodes that were never scheduled (circular dependency)
    unscheduled = node_ids - all_scheduled
    if unscheduled:
        logger.error(
            "Circular dependency detected - nodes never scheduled",
            unscheduled_nodes=sorted(unscheduled),
        )

    return results, results_by_id


def partition_task_results(
    results: JSONArray,
) -> tuple[JSONArray, JSONArray]:
    """Split results into validated and rejected, preserving stable shape."""
    validated: JSONArray = []
    rejected: JSONArray = []

    for result_value in results:
        if not isinstance(result_value, dict):
            continue
        result: JSONObject = result_value
        steps_value = result.get("steps")
        steps: JSONArray = (
            list(steps_value) if isinstance(steps_value, list) else []
        )
        if not steps:
            _add_rejected_result(result, validated, rejected)
            continue

        validated.append(
            {
                "id": result.get("id"),
                "task": result.get("task"),
                "steps": steps,
                "notes": result.get("notes"),
            }
        )

    return validated, rejected


def _add_rejected_result(
    result: JSONObject,
    validated: JSONArray,
    rejected: JSONArray,
) -> None:
    """Add a no-steps result to both validated and rejected lists."""
    payload = tool_error(
        "NO_STEPS_CREATED",
        "No steps created for the subtask.",
    )
    id_value = result.get("id")
    task_value = result.get("task")
    payload.update({"id": id_value, "task": task_value})
    rejected.append(payload)
    validated.append(
        {
            "id": id_value,
            "task": task_value,
            "steps": [],
            "notes": result.get("notes"),
        }
    )
