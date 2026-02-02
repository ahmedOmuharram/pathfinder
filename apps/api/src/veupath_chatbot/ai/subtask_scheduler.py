"""Run delegation graph nodes respecting dependency ordering."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from veupath_chatbot.platform.tool_errors import tool_error


async def run_nodes_with_dependencies(
    *,
    nodes_by_id: dict[str, dict[str, Any]],
    dependents: dict[str, list[str]],
    max_concurrency: int,
    run_node: Callable[[str, dict[str, Any], str | None], Awaitable[dict[str, Any]]],
    format_dependency_context: Callable[..., str | None],
    results_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Execute nodes concurrently while honoring their depends_on edges."""
    node_ids = set(nodes_by_id.keys())

    remaining_deps: dict[str, set[str]] = {
        node_id: {dep for dep in (node.get("depends_on") or []) if dep in node_ids}
        for node_id, node in nodes_by_id.items()
    }
    ready = [node_id for node_id, deps in remaining_deps.items() if not deps]
    running: dict[asyncio.Task, str] = {}
    results: list[dict[str, Any]] = []
    if results_by_id is None:
        results_by_id = {}

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def guarded_run(
        node_id: str, node: dict[str, Any], dependency_context: str | None
    ) -> dict[str, Any]:
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

        done, _ = await asyncio.wait(running.keys(), return_when=asyncio.FIRST_COMPLETED)
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
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split results into validated and rejected, preserving stable shape."""
    validated: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for result in results:
        steps = result.get("steps") if isinstance(result, dict) else None
        if not isinstance(steps, list) or not steps:
            payload = tool_error(
                "NO_STEPS_CREATED",
                "No steps created for the subtask.",
            )
            payload.update({"id": result.get("id"), "task": result.get("task")})
            rejected.append(payload)
            validated.append(
                {
                    "id": result.get("id"),
                    "task": result.get("task"),
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

