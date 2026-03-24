"""Sub-kani orchestration (delegation entrypoint + node execution).

This module contains the top-level delegation entry point and the node
execution functions (task nodes and combine nodes). Sub-kani execution
with retry logic lives in ``runner``, and SSE event emission in ``events``.
"""

import time

from veupath_chatbot.ai.orchestration.delegation import (
    CompiledCombine,
    CompiledNode,
    CompiledTask,
    DelegationPlan,
    build_delegation_plan,
)
from veupath_chatbot.ai.orchestration.results import (
    CombineResult,
    NodeResult,
    TaskResult,
)
from veupath_chatbot.ai.orchestration.scheduler import (
    partition_task_results,
    run_nodes_with_dependencies,
)
from veupath_chatbot.ai.orchestration.subkani.events import DelegationRunData
from veupath_chatbot.ai.orchestration.subkani.runner import run_subkani_task
from veupath_chatbot.ai.orchestration.subkani.utils import (
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
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.transport.http.schemas.sse import (
    GraphSnapshotContent,
    GraphSnapshotEventData,
    StrategyUpdateEventData,
)

logger = get_logger(__name__)


async def _run_combine_node(
    *,
    node_id: str,
    combine: CompiledCombine,
    results_by_id: dict[str, NodeResult],
    strategy_tools: StrategyTools,
    emit_event: EmitEvent,
) -> CombineResult:
    """Execute a combine node by chaining binary create_step calls."""
    operator = combine.operator.value

    resolved_inputs: list[str] = []
    missing: list[str] = []
    for ref in combine.inputs:
        dep_result = results_by_id.get(ref)
        step_id = dep_result.output_step_id if dep_result else None
        if step_id:
            resolved_inputs.append(step_id)
        else:
            missing.append(ref)

    if missing:
        return CombineResult(
            id=node_id,
            task=combine.task,
            operator=operator,
            inputs=list(combine.inputs),
            missing=missing,
            ok=False,
            error="Combine requires input steps.",
        )

    current_step_id = resolved_inputs[0]
    last_response: JSONObject | None = None
    for index, next_step_id in enumerate(resolved_inputs[1:], start=1):
        is_final = index == len(resolved_inputs) - 1
        response = await strategy_tools.create_step(
            primary_input_step_id=current_step_id,
            secondary_input_step_id=next_step_id,
            operator=operator,
            display_name=combine.display_name if is_final else None,
        )
        last_response = response
        if response.get("ok") is False or response.get("error"):
            return CombineResult(
                id=node_id,
                task=combine.task,
                operator=operator,
                ok=False,
                error="Combine failed while executing tool calls.",
            )
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
        "displayName": combine.display_name or combine.task or node_id,
    }
    graph_id_raw = (last_response or {}).get("graphId") if isinstance(last_response, dict) else None
    return CombineResult(
        id=node_id,
        task=combine.task,
        operator=operator,
        inputs=list(combine.inputs),
        steps=[step_payload],
        step_id=current_step_id,
        graph_id=str(graph_id_raw) if graph_id_raw is not None else None,
    )


async def _run_task_node(
    *,
    node_id: str,
    node: CompiledTask,
    goal: str,
    context: SubkaniContext,
    graph_id: str | None,
    dependency_context: str | None,
) -> TaskResult:
    """Execute a task node by running a sub-kani."""
    settings = get_settings()
    task_text = node.task
    instructions = node.instructions
    if instructions:
        task_text = f"{task_text}\n\nInstructions: {instructions}"
    extra_context = format_task_context(node.context)
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
        result = TaskResult(
            id=node_id,
            task=task_text,
            instructions=instructions,
            notes="failed",
            ok=False,
            error=str(exc),
        )
    # Stamp node identity onto the result (runner doesn't know the node_id).
    result.id = node_id
    result.task = task_text
    result.instructions = instructions
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

    logger.info("Spawning sub-kanis", count=len(compiled.tasks), site_id=context.site_id)
    start = time.monotonic()

    results_by_id: dict[str, NodeResult] = {}

    async def run_node(
        node_id: str, node: CompiledNode, dependency_context: str | None
    ) -> NodeResult:
        if isinstance(node, CompiledCombine):
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
        normalized=compiled.tasks,
        normalized_combines=compiled.combines,
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
    task_results: list[TaskResult] = []
    combine_results: list[CombineResult] = []
    combine_errors: list[CombineResult] = []
    for r in run_data.results:
        if isinstance(r, TaskResult):
            task_results.append(r)
        elif isinstance(r, CombineResult):
            if r.step_id:
                combine_results.append(r)
            if r.ok is False or r.error:
                combine_errors.append(r)

    task_dicts: JSONArray = [
        tr.model_dump(by_alias=True, exclude_none=True) for tr in task_results
    ]
    validated, rejected = partition_task_results(task_dicts)

    logger.info(
        "Sub-kani tasks completed",
        duration_ms=int((time.monotonic() - run_data.start) * 1000),
        results=len(validated),
        rejected=len(rejected),
    )

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

    tasks_serialized: JSONArray = [
        t.model_dump(by_alias=True, mode="json") for t in run_data.normalized
    ]
    combines_serialized: JSONArray = [
        c.model_dump(by_alias=True, mode="json") for c in run_data.normalized_combines
    ]

    return {
        "goal": goal,
        "tasks": tasks_serialized,
        "graphId": run_data.graph_id,
        "graphName": run_data.graph_name,
        "graphDescription": run_data.graph_description,
        "combines": combines_serialized,
        "combineResults": [cr.model_dump(by_alias=True, exclude_none=True) for cr in combine_results],
        "combineErrors": [ce.model_dump(by_alias=True, exclude_none=True) for ce in combine_errors],
        "results": validated,
        "rejected": rejected,
    }
