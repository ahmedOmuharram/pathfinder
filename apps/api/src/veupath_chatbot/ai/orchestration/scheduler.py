"""Run delegation graph nodes respecting dependency ordering."""

import asyncio
from collections.abc import Awaitable, Callable

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    as_json_array,
    as_json_object,
)

logger = get_logger(__name__)


def _compute_remaining_deps(
    nodes_by_id: dict[str, JSONObject],
    node_ids: set[str],
) -> dict[str, set[str]]:
    """Compute initial remaining dependencies for each node."""
    remaining_deps: dict[str, set[str]] = {}
    for node_id, node in nodes_by_id.items():
        depends_on_value = node.get("depends_on")
        if isinstance(depends_on_value, list):
            deps_list = as_json_array(depends_on_value)
            remaining_deps[node_id] = {
                dep for dep in deps_list if isinstance(dep, str) and dep in node_ids
            }
        else:
            remaining_deps[node_id] = set()
    return remaining_deps


async def _schedule_and_run(
    *,
    nodes_by_id: dict[str, JSONObject],
    dependents: dict[str, list[str]],
    remaining_deps: dict[str, set[str]],
    max_concurrency: int,
    run_node: Callable[[str, JSONObject, str | None], Awaitable[JSONObject]],
    format_dependency_context: Callable[..., str | None],
    results_by_id: dict[str, JSONObject],
) -> tuple[JSONArray, set[str]]:
    """Run nodes with concurrency control and dependency tracking."""
    ready = [node_id for node_id, deps in remaining_deps.items() if not deps]
    running: dict[asyncio.Task[JSONObject], str] = {}
    results: JSONArray = []
    all_scheduled: set[str] = set()
    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def guarded_run(
        node_id: str, node: JSONObject, dependency_context: str | None
    ) -> JSONObject:
        async with semaphore:
            return await run_node(node_id, node, dependency_context)

    while ready or running:
        _launch_ready_nodes(
            ready,
            running,
            all_scheduled,
            nodes_by_id,
            format_dependency_context,
            results_by_id,
            guarded_run,
            max_concurrency,
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
            if isinstance(result, dict):
                results_by_id[finished_id] = result
            for child in dependents.get(finished_id, []):
                remaining_deps[child].discard(finished_id)
                if not remaining_deps[child]:
                    ready.append(child)

    return results, all_scheduled


def _launch_ready_nodes(
    ready: list[str],
    running: dict[asyncio.Task[JSONObject], str],
    all_scheduled: set[str],
    nodes_by_id: dict[str, JSONObject],
    format_dependency_context: Callable[..., str | None],
    results_by_id: dict[str, JSONObject],
    guarded_run: Callable[..., Awaitable[JSONObject]],
    max_concurrency: int,
) -> None:
    """Launch as many ready nodes as concurrency allows."""
    while ready and len(running) < max(1, int(max_concurrency)):
        node_id = ready.pop()
        all_scheduled.add(node_id)
        node = nodes_by_id[node_id]
        dependency_context = format_dependency_context(
            task_id=node_id,
            tasks_by_id=nodes_by_id,
            results_by_id=results_by_id,
        )
        running_task = asyncio.create_task(
            guarded_run(node_id, node, dependency_context)
        )
        running[running_task] = node_id


async def run_nodes_with_dependencies(
    *,
    nodes_by_id: dict[str, JSONObject],
    dependents: dict[str, list[str]],
    max_concurrency: int,
    run_node: Callable[[str, JSONObject, str | None], Awaitable[JSONObject]],
    format_dependency_context: Callable[..., str | None],
    results_by_id: dict[str, JSONObject] | None = None,
) -> tuple[JSONArray, dict[str, JSONObject]]:
    """Execute nodes concurrently while honoring their depends_on edges."""
    node_ids = set(nodes_by_id.keys())
    remaining_deps = _compute_remaining_deps(nodes_by_id, node_ids)
    if results_by_id is None:
        results_by_id = {}

    results, all_scheduled = await _schedule_and_run(
        nodes_by_id=nodes_by_id,
        dependents=dependents,
        remaining_deps=remaining_deps,
        max_concurrency=max_concurrency,
        run_node=run_node,
        format_dependency_context=format_dependency_context,
        results_by_id=results_by_id,
    )

    # Report any nodes that were never scheduled (circular dependency)
    unscheduled = node_ids - all_scheduled
    if unscheduled:
        logger.error(
            "Circular dependency detected - nodes never scheduled",
            unscheduled_nodes=sorted(unscheduled),
        )
        for node_id in unscheduled:
            results.append(
                tool_error(
                    "CIRCULAR_DEPENDENCY",
                    f"Task '{node_id}' has circular dependencies and was skipped.",
                )
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
        result = as_json_object(result_value)
        steps_value = result.get("steps")
        steps: JSONArray = (
            as_json_array(steps_value) if isinstance(steps_value, list) else []
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
