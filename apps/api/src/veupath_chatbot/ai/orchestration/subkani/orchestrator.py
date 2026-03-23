"""Sub-kani orchestration (delegation entrypoint + node execution).

This module contains the top-level delegation entry point and the node
execution functions (task nodes and combine nodes). Sub-kani execution
with retry logic lives in ``runner``, and SSE event emission in ``events``.
"""

import time
from typing import cast

from veupath_chatbot.ai.orchestration.delegation import (
    DelegationPlan,
    build_delegation_plan,
)
from veupath_chatbot.ai.orchestration.scheduler import (
    partition_task_results,
    run_nodes_with_dependencies,
)
from veupath_chatbot.ai.orchestration.subkani.events import DelegationRunData
from veupath_chatbot.ai.orchestration.subkani.runner import run_subkani_task
from veupath_chatbot.ai.orchestration.subkani.utils import (
    extract_primary_step_id,
    format_dependency_context,
    format_task_context,
)
from veupath_chatbot.ai.orchestration.types import EmitEvent, SubkaniContext
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.domain.strategy.metadata import derive_graph_metadata
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.transport.http.schemas.sse import (
    GraphSnapshotContent,
    GraphSnapshotEventData,
    StrategyUpdateEventData,
)

logger = get_logger(__name__)


async def _run_combine_node(
    *,
    node_id: str,
    combine: JSONObject,
    results_by_id: dict[str, JSONObject],
    strategy_tools: StrategyTools,
    emit_event: EmitEvent,
) -> JSONObject:
    """Execute a combine node by chaining binary create_step calls."""
    input_refs_raw = combine.get("inputs")
    input_refs = input_refs_raw if isinstance(input_refs_raw, list) else []
    operator = combine.get("operator")

    resolved_inputs: list[str] = []
    missing: list[str] = []
    for ref_value in input_refs:
        ref = str(ref_value) if ref_value is not None else ""
        dep_result = results_by_id.get(ref)
        step_id = extract_primary_step_id(dep_result)
        if step_id:
            resolved_inputs.append(step_id)
        else:
            missing.append(ref)

    if missing:
        payload = tool_error(
            "MISSING_COMBINE_INPUTS",
            "Combine requires input steps.",
            missing=cast("JSONArray", missing),
        )
        payload.update(
            {
                "id": node_id,
                "task": combine.get("task"),
                "kind": "combine",
                "missing": cast("JSONArray", missing),
                "steps": [],
            }
        )
        return payload

    current_step_id = resolved_inputs[0]
    last_response: JSONObject | None = None
    for index, next_step_id in enumerate(resolved_inputs[1:], start=1):
        is_final = index == len(resolved_inputs) - 1
        response = await strategy_tools.create_step(
            primary_input_step_id=current_step_id,
            secondary_input_step_id=next_step_id,
            operator=str(operator),
            display_name=combine.get("display_name") if is_final else None,
            upstream=combine.get("upstream"),
            downstream=combine.get("downstream"),
        )
        last_response = response
        if response.get("ok") is False or response.get("error"):
            payload = tool_error(
                "COMBINE_FAILED",
                "Combine failed while executing tool calls.",
                response=response,
            )
            payload.update(
                {
                    "id": node_id,
                    "task": combine.get("task"),
                    "kind": "combine",
                    "steps": [],
                }
            )
            return payload
        await emit_event(
            {
                "type": "strategy_update",
                "data": StrategyUpdateEventData(
                    graph_id=response.get("graphId"),
                    step=response,
                ).model_dump(by_alias=True, exclude_none=True),
            }
        )
        current_step_id = response.get("stepId") or current_step_id

    step_payload: JSONObject = {
        "stepId": current_step_id,
        "displayName": combine.get("display_name") or combine.get("task") or node_id,
    }
    return {
        "id": node_id,
        "task": combine.get("task"),
        "kind": "combine",
        "operator": operator,
        "inputs": input_refs,
        "steps": [step_payload],
        "stepId": current_step_id,
        "graphId": (last_response or {}).get("graphId")
        if isinstance(last_response, dict)
        else None,
    }


async def _run_task_node(
    *,
    node_id: str,
    node: JSONObject,
    goal: str,
    context: SubkaniContext,
    graph_id: str | None,
    dependency_context: str | None,
) -> JSONObject:
    """Execute a task node by running a sub-kani."""
    settings = get_settings()
    task_text = str(node.get("task") or "").strip()
    instructions = str(node.get("instructions") or "").strip()
    if instructions:
        task_text = f"{task_text}\n\nInstructions: {instructions}"
    extra_context = format_task_context(node.get("context"))
    if extra_context:
        dependency_context = (
            ((dependency_context + "\n\n") if dependency_context else "")
            + "Planner-provided context (JSON/text):\n"
            + extra_context
        )
    task_context = SubkaniContext(
        site_id=context.site_id,
        strategy_session=context.strategy_session,
        chat_history=context.chat_history,
        emit_event=context.emit_event,
        subkani_timeout_seconds=settings.subkani_timeout_seconds,
        engine_factory=context.engine_factory,
    )
    try:
        result = await run_subkani_task(
            task=task_text,
            goal=goal,
            context=task_context,
            graph_id=graph_id,
            dependency_context=dependency_context,
        )
    except (AppError, OSError, TimeoutError) as exc:
        logger.error(
            "Sub-kani task crashed",
            task=task_text,
            node_id=node_id,
            error=str(exc),
            exc_info=True,
        )
        result = tool_error(
            "SUBKANI_FAILED",
            str(exc),
            notes="failed",
            nodeId=node_id,
            task=task_text,
        )
    if isinstance(result, dict):
        result["id"] = node_id
        result["task"] = task_text
        result["kind"] = "task"
        result["instructions"] = instructions
    return result


async def delegate_strategy_subtasks(
    *,
    goal: str,
    context: SubkaniContext,
    strategy_tools: StrategyTools,
    plan: JSONObject | None = None,
) -> JSONObject:
    settings = get_settings()
    compiled = build_delegation_plan(goal=goal, plan=plan)
    if isinstance(compiled, dict):
        return compiled
    if not isinstance(compiled, DelegationPlan):
        return tool_error(
            "DELEGATION_PLAN_INVALID",
            "Delegation plan normalization returned an unexpected type.",
            goal=goal,
            receivedType=type(compiled).__name__,
        )

    normalized = compiled.tasks
    normalized_combines = compiled.combines
    nodes_by_id = compiled.nodes_by_id
    dependents = compiled.dependents

    graph_name, graph_description = derive_graph_metadata(goal)
    graph = context.strategy_session.get_graph(None)
    graph_id = graph.id if graph else None
    if not graph:
        graph = context.strategy_session.create_graph(graph_name)
        graph_id = graph.id
    await context.emit_event(
        {
            "type": "graph_snapshot",
            "data": GraphSnapshotEventData(
                graph_snapshot=GraphSnapshotContent.model_validate(
                    strategy_tools._build_graph_snapshot(graph)
                ),
            ).model_dump(by_alias=True, exclude_none=True),
        }
    )

    logger.info("Spawning sub-kanis", count=len(normalized), site_id=context.site_id)
    start = time.monotonic()

    results_by_id: dict[str, JSONObject] = {}

    async def run_node(
        node_id: str, node: JSONObject, dependency_context: str | None
    ) -> JSONObject:
        kind = node.get("kind")
        if kind == "combine":
            return await _run_combine_node(
                node_id=node_id,
                combine=node,
                results_by_id=results_by_id,
                strategy_tools=strategy_tools,
                emit_event=context.emit_event,
            )
        return await _run_task_node(
            node_id=node_id,
            node=node,
            goal=goal,
            context=context,
            graph_id=graph_id,
            dependency_context=dependency_context,
        )

    results, _results_by_id = await run_nodes_with_dependencies(
        nodes_by_id=nodes_by_id,
        dependents=dependents,
        max_concurrency=settings.subkani_max_concurrency,
        run_node=run_node,
        format_dependency_context=format_dependency_context,
        results_by_id=results_by_id,
    )

    run_data = DelegationRunData(
        graph=graph,
        graph_id=graph_id,
        graph_name=graph_name,
        graph_description=graph_description,
        normalized=normalized,
        normalized_combines=normalized_combines,
        results=results,
        start=start,
    )
    return await _build_delegation_response(
        goal=goal,
        run_data=run_data,
        strategy_tools=strategy_tools,
        emit_event=context.emit_event,
    )


async def _build_delegation_response(
    *,
    goal: str,
    run_data: DelegationRunData,
    strategy_tools: StrategyTools,
    emit_event: EmitEvent,
) -> JSONObject:
    """Build the final delegation response from results."""
    task_results: JSONArray = [
        cast("JSONValue", r)
        for r in run_data.results
        if isinstance(r, dict) and r.get("kind") == "task"
    ]
    validated, rejected = partition_task_results(task_results)

    logger.info(
        "Sub-kani tasks completed",
        duration_ms=int((time.monotonic() - run_data.start) * 1000),
        results=len(validated),
        rejected=len(rejected),
    )

    combine_results: JSONArray = [
        cast("JSONValue", r)
        for r in run_data.results
        if isinstance(r, dict) and r.get("kind") == "combine" and r.get("stepId")
    ]
    combine_errors: JSONArray = [
        cast("JSONValue", r)
        for r in run_data.results
        if isinstance(r, dict)
        and r.get("kind") == "combine"
        and (r.get("ok") is False or r.get("error"))
    ]

    if isinstance(run_data.graph, StrategyGraph):
        run_data.graph.name = run_data.graph_name
        run_data.graph.description = run_data.graph_description
        run_data.graph.save_history("Updated strategy metadata from delegation")
        await emit_event(
            {
                "type": "graph_snapshot",
                "data": GraphSnapshotEventData(
                    graph_snapshot=GraphSnapshotContent.model_validate(
                        strategy_tools._build_graph_snapshot(run_data.graph)
                    ),
                ).model_dump(by_alias=True, exclude_none=True),
            }
        )

    return {
        "goal": goal,
        "tasks": run_data.normalized,
        "graphId": run_data.graph_id,
        "graphName": run_data.graph_name,
        "graphDescription": run_data.graph_description,
        "combines": run_data.normalized_combines,
        "combineResults": combine_results,
        "combineErrors": combine_errors,
        "results": validated,
        "rejected": rejected,
    }
