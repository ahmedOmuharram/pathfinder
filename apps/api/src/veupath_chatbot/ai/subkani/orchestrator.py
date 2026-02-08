"""Sub-kani orchestration (dependency scheduling + retries).

This module extracts the "spawn sub-agents, run tasks with dependencies, emit events"
workflow out of the main agent runtime to keep concerns separated.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from kani.engines.openai import OpenAIEngine
from kani.models import ChatRole

from veupath_chatbot.ai.delegation_plan import DelegationPlan, build_delegation_plan
from veupath_chatbot.ai.graph_metadata import derive_graph_metadata
from veupath_chatbot.ai.subkani_utils import (
    consume_subkani_round,
    extract_primary_step_id,
    format_dependency_context,
    format_task_context,
)
from veupath_chatbot.ai.subkani.prompts import build_subkani_round_prompt
from veupath_chatbot.ai.subtask_agent import SubtaskAgent
from veupath_chatbot.ai.subtask_scheduler import (
    partition_task_results,
    run_nodes_with_dependencies,
)
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.tool_errors import tool_error

logger = get_logger(__name__)

EmitEvent = Callable[[dict[str, Any]], Awaitable[None]]


async def run_subkani_task(
    *,
    task: str,
    goal: str,
    site_id: str,
    strategy_session,
    graph_id: str | None,
    dependency_context: str | None,
    chat_history,
    emit_event: EmitEvent,
    subkani_timeout_seconds: int,
) -> dict[str, Any]:
    settings = get_settings()
    engine = OpenAIEngine(
        api_key=settings.openai_api_key,
        model=settings.subkani_model,
        temperature=settings.subkani_temperature,
        top_p=settings.subkani_top_p,
    )

    if not graph_id:
        graph = strategy_session.get_graph(None)
        graph_id = graph.id if graph else None
    if not graph_id:
        graph = strategy_session.create_graph("Draft Strategy")
        graph_id = graph.id
    elif not strategy_session.get_graph(graph_id):
        graph = strategy_session.create_graph("Draft Strategy", graph_id=graph_id)
        graph_id = graph.id

    clean_history = [
        message
        for message in chat_history
        if message.role != ChatRole.FUNCTION
        and not getattr(message, "tool_calls", None)
        and getattr(message, "tool_call_id", None) is None
    ]

    sub_kani = SubtaskAgent(
        engine=engine,
        site_id=site_id,
        session=strategy_session,
        graph_id=graph_id,
        chat_history=clean_history,
    )

    await emit_event({"type": "subkani_task_start", "data": {"task": task}})
    prompt = build_subkani_round_prompt(
        task=task,
        goal=goal,
        graph_id=str(graph_id),
        dependency_context=dependency_context,
    )

    created_steps: list[dict[str, Any]] = []
    emitted_step_ids: set[str] = set()
    last_errors: list[str] = []

    # If a sub-kani produces no steps, treat it as a retryable failure.
    # These retries are intentionally more aggressive than tool-level retries
    # because "no_steps" usually means "wrong search" or "missing required params".
    for attempt in range(5):
        try:
            _, round_steps, round_errors = await asyncio.wait_for(
                consume_subkani_round(
                    sub_kani=sub_kani,
                    emit_event=emit_event,
                    task=task,
                    round_prompt=prompt,
                ),
                timeout=subkani_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await emit_event(
                {"type": "subkani_task_end", "data": {"task": task, "status": "timeout"}}
            )
            return {"task": task, "steps": [], "notes": "timeout"}

        last_errors = round_errors
        created_steps.extend(round_steps)
        if created_steps:
            graph = strategy_session.get_graph(graph_id)
            for step in created_steps:
                step_id = step.get("stepId")
                if not step_id or step_id in emitted_step_ids:
                    continue
                emitted_step_ids.add(step_id)
                await emit_event(
                    {
                        "type": "strategy_update",
                        "data": {
                            "graphId": step.get("graphId") or graph_id,
                            "step": step,
                            "allSteps": [
                                {
                                    "stepId": sid,
                                    "kind": getattr(s, "infer_kind", lambda: None)(),
                                    "displayName": s.display_name,
                                }
                                for sid, s in (graph.steps.items() if graph else [])
                            ],
                        },
                    }
                )
                snapshot = step.get("graphSnapshot")
                if isinstance(snapshot, dict):
                    await emit_event(
                        {
                            "type": "graph_snapshot",
                            "data": {
                                "graphId": snapshot.get("graphId") or graph_id,
                                "graphSnapshot": snapshot,
                            },
                        }
                    )
            await emit_event(
                {"type": "subkani_task_end", "data": {"task": task, "status": "done"}}
            )
            return {"task": task, "steps": created_steps, "notes": "created"}

        if attempt < 4:
            await emit_event(
                {"type": "subkani_task_retry", "data": {"task": task, "attempt": attempt + 2}}
            )
            error_hint = "; ".join(last_errors) if last_errors else "no steps created"
            prompt = (
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

    await emit_event(
        {"type": "subkani_task_end", "data": {"task": task, "status": "no_steps"}}
    )
    return {"task": task, "steps": [], "notes": "no_steps", "errors": last_errors}


async def delegate_strategy_subtasks(
    *,
    goal: str,
    site_id: str,
    strategy_session,
    strategy_tools,
    emit_event: EmitEvent,
    chat_history,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    compiled = build_delegation_plan(
        goal=goal,
        plan=plan,
    )
    if isinstance(compiled, dict):
        # Plan validation error payload; return immediately.
        return compiled
    if not isinstance(compiled, DelegationPlan):
        # Defensive: should never happen, but prevents confusing attribute errors.
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
    graph = strategy_session.get_graph(None)
    graph_id = graph.id if graph else None
    if not graph:
        graph = strategy_session.create_graph(graph_name)
        graph_id = graph.id
    await emit_event(
        {"type": "graph_snapshot", "data": {"graphSnapshot": strategy_tools._build_graph_snapshot(graph)}}
    )

    logger.info("Spawning sub-kanis", count=len(normalized), site_id=site_id)
    start = time.monotonic()

    results_by_id: dict[str, dict[str, Any]] = {}

    async def run_node(node_id: str, node: dict[str, Any], dependency_context: str | None) -> dict:
        kind = node.get("kind")
        if kind == "combine":
            del dependency_context
            combine = node
            input_refs = combine.get("inputs") or []
            operator = combine.get("operator")

            resolved_inputs: list[str] = []
            missing: list[str] = []
            for ref in input_refs:
                dep_result = results_by_id.get(str(ref))
                step_id = extract_primary_step_id(dep_result)
                if step_id:
                    resolved_inputs.append(step_id)
                else:
                    missing.append(str(ref))

            if missing:
                payload = tool_error(
                    "MISSING_COMBINE_INPUTS",
                    "Combine requires input steps.",
                    missing=missing,
                )
                payload.update(
                    {
                        "id": node_id,
                        "task": combine.get("task"),
                        "kind": "combine",
                        "missing": missing,
                        "steps": [],
                    }
                )
                return payload

            current_step_id = resolved_inputs[0]
            last_response: dict[str, Any] | None = None
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
                    {"type": "strategy_update", "data": {"graphId": response.get("graphId"), "step": response}}
                )
                current_step_id = response.get("stepId") or current_step_id

            step_payload = {
                "stepId": current_step_id,
                "displayName": combine.get("display_name") or combine.get("task") or node_id,
            }
            return {
                "id": node_id,
                "task": combine.get("task"),
                "kind": "combine",
                "operator": operator,
                "inputs": list(input_refs),
                "steps": [step_payload],
                "stepId": current_step_id,
                "graphId": (last_response or {}).get("graphId") if isinstance(last_response, dict) else None,
            }

        task_text = str(node.get("task") or "").strip()
        hint = str(node.get("hint") or "").strip()
        if hint:
            task_text = f"{task_text}\n\nHint: {hint}"
        extra_context = format_task_context(node.get("context"))
        if extra_context:
            dependency_context = (
                (dependency_context + "\n\n") if dependency_context else ""
            ) + "Planner-provided context (JSON/text):\n" + extra_context
        try:
            result = await run_subkani_task(
                task=task_text,
                goal=goal,
                site_id=site_id,
                strategy_session=strategy_session,
                graph_id=graph_id,
                dependency_context=dependency_context,
                chat_history=chat_history,
                emit_event=emit_event,
                subkani_timeout_seconds=settings.subkani_timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover
            result = tool_error("SUBKANI_FAILED", str(exc), notes="failed")
        if isinstance(result, dict):
            result["id"] = node_id
            result["task"] = task_text
            result["kind"] = "task"
        return result

    results, _results_by_id = await run_nodes_with_dependencies(
        nodes_by_id=nodes_by_id,
        dependents=dependents,
        max_concurrency=settings.subkani_max_concurrency,
        run_node=run_node,
        format_dependency_context=format_dependency_context,
        results_by_id=results_by_id,
    )
    task_results = [r for r in results if isinstance(r, dict) and r.get("kind") == "task"]
    validated, rejected = partition_task_results(task_results)

    logger.info(
        "Sub-kani tasks completed",
        duration_ms=int((time.monotonic() - start) * 1000),
        results=len(validated),
        rejected=len(rejected),
    )

    combine_results = [r for r in results if isinstance(r, dict) and r.get("kind") == "combine" and r.get("stepId")]
    combine_errors = [
        r
        for r in results
        if isinstance(r, dict)
        and r.get("kind") == "combine"
        and (r.get("ok") is False or r.get("error"))
    ]

    if graph.current_strategy:
        graph.current_strategy.name = graph_name
        graph.current_strategy.description = graph_description
        graph.name = graph_name
        graph.save_history("Updated strategy metadata from delegation")
        await emit_event(
            {"type": "graph_snapshot", "data": {"graphSnapshot": strategy_tools._build_graph_snapshot(graph)}}
        )

    return {
        "goal": goal,
        "tasks": normalized,
        "graphId": graph_id,
        "graphName": graph_name,
        "graphDescription": graph_description,
        "combines": normalized_combines,
        "combineResults": combine_results,
        "combineErrors": combine_errors,
        "results": validated,
        "rejected": rejected,
    }

