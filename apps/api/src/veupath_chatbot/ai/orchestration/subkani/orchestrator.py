"""Sub-kani orchestration (dependency scheduling + retries).

This module extracts the "spawn sub-agents, run tasks with dependencies, emit events"
workflow out of the main agent runtime to keep concerns separated.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from kani.engines.base import BaseEngine
from kani.models import ChatMessage, ChatRole
from shared_py.defaults import DEFAULT_STREAM_NAME

from veupath_chatbot.ai.agents.subtask import SubtaskAgent
from veupath_chatbot.ai.engines.cached_anthropic import CachedAnthropicEngine
from veupath_chatbot.ai.engines.responses_openai import ResponsesOpenAIEngine
from veupath_chatbot.ai.models.pricing import estimate_cost as _estimate_subkani_cost
from veupath_chatbot.ai.orchestration.delegation import (
    DelegationPlan,
    build_delegation_plan,
)
from veupath_chatbot.ai.orchestration.scheduler import (
    partition_task_results,
    run_nodes_with_dependencies,
)
from veupath_chatbot.ai.orchestration.subkani.prompts import build_subkani_round_prompt
from veupath_chatbot.ai.orchestration.subkani.utils import (
    consume_subkani_round,
    extract_primary_step_id,
    format_dependency_context,
    format_task_context,
    get_round_result,
)
from veupath_chatbot.ai.orchestration.types import EmitEvent, SubkaniContext
from veupath_chatbot.ai.tools.strategy_tools import StrategyTools
from veupath_chatbot.domain.strategy.metadata import derive_graph_metadata
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.platform.config import Settings, get_settings
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.transport.http.schemas.sse import (
    SubKaniTaskEndEventData,
    SubKaniTaskStartEventData,
)

logger = get_logger(__name__)

_MAX_SUBKANI_RETRIES = 5
_LAST_RETRY_INDEX = _MAX_SUBKANI_RETRIES - 1


@dataclass
class SubkaniRunState:
    """State for a single subkani run attempt."""

    sub_kani: SubtaskAgent
    task: str
    graph_id: str
    subkani_model_id: str
    prompt: str


@dataclass
class DelegationRunData:
    """Aggregated data from a delegation run for response construction."""

    graph: object
    graph_id: str | None
    graph_name: str
    graph_description: str
    normalized: JSONArray
    normalized_combines: JSONArray
    results: JSONArray
    start: float


def _derive_model_id(engine: BaseEngine) -> str:
    """Derive a catalog-style model ID from an engine instance."""
    model = getattr(engine, "model", "unknown")
    if isinstance(engine, CachedAnthropicEngine):
        return f"anthropic/{model}"
    if isinstance(engine, ResponsesOpenAIEngine):
        return f"openai/{model}"
    return model


def _clean_chat_history(context: SubkaniContext) -> list[ChatMessage]:
    """Remove tool-related messages from chat history for sub-kani use."""
    return [
        message
        for message in context.chat_history
        if message.role != ChatRole.FUNCTION
        and not getattr(message, "tool_calls", None)
        and getattr(message, "tool_call_id", None) is None
    ]


def _resolve_graph_id(
    strategy_session: StrategySession,
    graph_id: str | None,
) -> str:
    """Resolve or create a graph ID for the sub-kani."""
    if not graph_id:
        graph = strategy_session.get_graph(None)
        graph_id = graph.id if graph else None
    if not graph_id:
        graph = strategy_session.create_graph(DEFAULT_STREAM_NAME)
        return graph.id
    if not strategy_session.get_graph(graph_id):
        graph = strategy_session.create_graph(DEFAULT_STREAM_NAME, graph_id=graph_id)
        return graph.id
    return graph_id


def _create_subkani_engine(
    settings: Settings,
    engine_factory: Callable[[], BaseEngine] | None,
) -> BaseEngine:
    """Create the engine for a sub-kani agent."""
    if engine_factory is not None:
        return engine_factory()
    return ResponsesOpenAIEngine(
        api_key=settings.openai_api_key,
        model=settings.subkani_model,
        temperature=settings.subkani_temperature,
        top_p=settings.subkani_top_p,
    )


async def _emit_step_events(
    *,
    created_steps: JSONArray,
    emitted_step_ids: set[str],
    graph: object,
    graph_id: str | None,
    emit_event: EmitEvent,
) -> None:
    """Emit strategy_update and graph_snapshot events for newly created steps."""
    if not isinstance(graph, StrategyGraph):
        return

    for step_value in created_steps:
        if not isinstance(step_value, dict):
            continue
        step = step_value
        step_id_raw = step.get("stepId")
        step_id = step_id_raw if isinstance(step_id_raw, str) else None
        if not step_id or step_id in emitted_step_ids:
            continue
        emitted_step_ids.add(step_id)
        graph_id_raw = step.get("graphId")
        graph_id_str = graph_id_raw if isinstance(graph_id_raw, str) else graph_id
        await emit_event(
            {
                "type": "strategy_update",
                "data": {
                    "graphId": graph_id_str,
                    "step": step,
                    "allSteps": [
                        {
                            "stepId": sid,
                            "kind": getattr(s, "infer_kind", lambda: None)(),
                            "displayName": s.display_name,
                        }
                        for sid, s in graph.steps.items()
                    ],
                },
            }
        )
        snapshot_raw = step.get("graphSnapshot")
        snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else None
        if snapshot:
            await emit_event(
                {
                    "type": "graph_snapshot",
                    "data": {
                        "graphId": snapshot.get("graphId") or graph_id,
                        "graphSnapshot": snapshot,
                    },
                }
            )


async def _emit_task_end(
    *,
    task: str,
    subkani_model_id: str,
    emit_event: EmitEvent,
    status: str = "done",
) -> None:
    """Emit a subkani_task_end event with token usage."""
    round_result = get_round_result(task)
    sub_cost = _estimate_subkani_cost(
        subkani_model_id,
        prompt_tokens=round_result.prompt_tokens if round_result else 0,
        completion_tokens=round_result.completion_tokens if round_result else 0,
    )
    await emit_event(
        {
            "type": "subkani_task_end",
            "data": SubKaniTaskEndEventData(
                task=task,
                status=status,
                modelId=subkani_model_id,
                promptTokens=round_result.prompt_tokens if round_result else 0,
                completionTokens=round_result.completion_tokens if round_result else 0,
                llmCallCount=round_result.llm_call_count if round_result else 0,
                estimatedCostUsd=sub_cost,
            ).model_dump(by_alias=True),
        }
    )


def _build_retry_prompt(
    task: str,
    graph_id: str | None,
    last_errors: list[str],
) -> str:
    """Build a retry prompt for a sub-kani that produced no steps."""
    error_hint = "; ".join(last_errors) if last_errors else "no steps created"
    return (
        "Retry the task and you MUST create at least one valid step.\n"
        "Before creating anything:\n"
        "- Use get_record_types() if record type is unclear.\n"
        "- Use search_for_searches(query) to find relevant searches.\n"
        "- Use get_search_parameters(record_type, search_name) to learn required params.\n"
        "Execution rules:\n"
        "- All parameter values must be strings.\n"
        "- Use create_step for all step creation.\n"
        "- If the step depends on a prior step, set primary_input_step_id.\n"
        "- If the step needs a binary operator, set secondary_input_step_id + operator.\n"
        f"Previous issue: {error_hint}\n"
        f"Task: {task}\n"
        f"Graph: {graph_id}\n"
    )


async def run_subkani_task(
    *,
    task: str,
    goal: str,
    context: SubkaniContext,
    graph_id: str | None,
    dependency_context: str | None,
) -> JSONObject:
    settings = get_settings()
    engine = _create_subkani_engine(settings, context.engine_factory)
    subkani_model_id = _derive_model_id(engine)
    resolved_graph_id = _resolve_graph_id(context.strategy_session, graph_id)
    clean_history = _clean_chat_history(context)

    sub_kani = SubtaskAgent(
        engine=engine,
        site_id=context.site_id,
        session=context.strategy_session,
        graph_id=resolved_graph_id,
        chat_history=clean_history,
    )

    await context.emit_event(
        {
            "type": "subkani_task_start",
            "data": SubKaniTaskStartEventData(
                task=task, modelId=subkani_model_id
            ).model_dump(by_alias=True),
        }
    )
    prompt = build_subkani_round_prompt(
        task=task,
        goal=goal,
        graph_id=str(resolved_graph_id),
        dependency_context=dependency_context,
    )

    run_state = SubkaniRunState(
        sub_kani=sub_kani,
        task=task,
        graph_id=resolved_graph_id,
        subkani_model_id=subkani_model_id,
        prompt=prompt,
    )
    return await _run_subkani_retry_loop(run_state=run_state, context=context)


async def _run_subkani_retry_loop(
    *,
    run_state: SubkaniRunState,
    context: SubkaniContext,
) -> JSONObject:
    """Execute the sub-kani with retry logic for no-step results."""
    created_steps: JSONArray = []
    emitted_step_ids: set[str] = set()
    last_errors: list[str] = []

    graph = context.strategy_session.get_graph(run_state.graph_id)
    roots_before: set[str] = set(graph.roots) if graph else set()
    prompt = run_state.prompt

    for attempt in range(_MAX_SUBKANI_RETRIES):
        try:
            _, round_steps, round_errors = await asyncio.wait_for(
                consume_subkani_round(
                    sub_kani=run_state.sub_kani,
                    emit_event=context.emit_event,
                    task=run_state.task,
                    round_prompt=prompt,
                ),
                timeout=context.subkani_timeout_seconds,
            )
        except TimeoutError:
            await context.emit_event(
                {
                    "type": "subkani_task_end",
                    "data": SubKaniTaskEndEventData(
                        task=run_state.task,
                        status="timeout",
                        modelId=run_state.subkani_model_id,
                    ).model_dump(by_alias=True),
                }
            )
            return {"task": run_state.task, "steps": [], "notes": "timeout"}

        last_errors = round_errors
        created_steps.extend(round_steps)
        if created_steps:
            return await _finalize_successful_run(
                run_state=run_state,
                context=context,
                created_steps=created_steps,
                emitted_step_ids=emitted_step_ids,
                roots_before=roots_before,
            )

        if attempt < _LAST_RETRY_INDEX:
            await context.emit_event(
                {
                    "type": "subkani_task_retry",
                    "data": {"task": run_state.task, "attempt": attempt + 2},
                }
            )
            prompt = _build_retry_prompt(
                run_state.task, run_state.graph_id, last_errors
            )

    await context.emit_event(
        {
            "type": "subkani_task_end",
            "data": SubKaniTaskEndEventData(
                task=run_state.task,
                status="no_steps",
                modelId=run_state.subkani_model_id,
            ).model_dump(by_alias=True),
        }
    )
    return {
        "task": run_state.task,
        "steps": [],
        "notes": "no_steps",
        "errors": cast("JSONArray", last_errors),
    }


async def _finalize_successful_run(
    *,
    run_state: SubkaniRunState,
    context: SubkaniContext,
    created_steps: JSONArray,
    emitted_step_ids: set[str],
    roots_before: set[str],
) -> JSONObject:
    """Finalize a successful sub-kani run: emit events and return result."""
    graph = context.strategy_session.get_graph(run_state.graph_id)
    await _emit_step_events(
        created_steps=created_steps,
        emitted_step_ids=emitted_step_ids,
        graph=graph,
        graph_id=run_state.graph_id,
        emit_event=context.emit_event,
    )
    roots_after: set[str] = set(graph.roots) if graph else set()
    new_roots = roots_after - roots_before
    if len(new_roots) != 1:
        logger.warning(
            "Sub-kani subtree-root contract violation",
            task=run_state.task,
            new_roots=sorted(new_roots),
            expected=1,
            actual=len(new_roots),
        )
    subtree_root = next(iter(new_roots)) if len(new_roots) == 1 else None

    await _emit_task_end(
        task=run_state.task,
        subkani_model_id=run_state.subkani_model_id,
        emit_event=context.emit_event,
    )
    result: JSONObject = {
        "task": run_state.task,
        "steps": created_steps,
        "notes": "created",
    }
    if subtree_root:
        result["subtreeRoot"] = subtree_root
    return result


# -- Delegation entrypoint ---------------------------------------------------


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
                "data": {"graphId": response.get("graphId"), "step": response},
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
            "data": {"graphSnapshot": strategy_tools._build_graph_snapshot(graph)},
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

    if isinstance(run_data.graph, StrategyGraph) and run_data.graph.current_strategy:
        run_data.graph.current_strategy.name = run_data.graph_name
        run_data.graph.current_strategy.description = run_data.graph_description
        run_data.graph.name = run_data.graph_name
        run_data.graph.save_history("Updated strategy metadata from delegation")
        await emit_event(
            {
                "type": "graph_snapshot",
                "data": {
                    "graphSnapshot": strategy_tools._build_graph_snapshot(
                        run_data.graph
                    )
                },
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
