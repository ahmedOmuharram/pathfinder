"""Run delegation graph nodes respecting dependency ordering."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    as_json_array,
    as_json_object,
)


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
    ready = [node_id for node_id, deps in remaining_deps.items() if not deps]
    running: dict[asyncio.Task[JSONObject], str] = {}
    results: JSONArray = []
    if results_by_id is None:
        results_by_id = {}

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def guarded_run(
        node_id: str, node: JSONObject, dependency_context: str | None
    ) -> JSONObject:
        async with semaphore:
            return await run_node(node_id, node, dependency_context)

    while ready or running:
        while ready and len(running) < max(1, int(max_concurrency)):
            node_id = ready.pop()
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
            payload = tool_error(
                "NO_STEPS_CREATED",
                "No steps created for the subtask.",
            )
            id_value = result.get("id")
            task_value = result.get("task")
            payload.update(
                {
                    "id": id_value,
                    "task": task_value,
                }
            )
            rejected.append(payload)
            validated.append(
                {
                    "id": id_value,
                    "task": task_value,
                    "steps": [],
                    "notes": result.get("notes"),
                }
            )
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
