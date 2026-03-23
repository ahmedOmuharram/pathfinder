"""Single sub-kani execution and retry logic.

Handles creating a sub-kani agent, running it against a task with retries,
and finalizing successful runs by emitting events and computing subtree roots.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from kani.engines.base import BaseEngine
from kani.models import ChatMessage, ChatRole
from shared_py.defaults import DEFAULT_STREAM_NAME

from veupath_chatbot.ai.agents.subtask import SubtaskAgent
from veupath_chatbot.ai.engines.cached_anthropic import CachedAnthropicEngine
from veupath_chatbot.ai.engines.responses_openai import ResponsesOpenAIEngine
from veupath_chatbot.ai.orchestration.subkani.events import (
    _emit_step_events,
    _emit_task_end,
)
from veupath_chatbot.ai.orchestration.subkani.prompts import build_subkani_round_prompt
from veupath_chatbot.ai.orchestration.subkani.utils import consume_subkani_round
from veupath_chatbot.ai.orchestration.types import SubkaniContext
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.platform.config import Settings, get_settings
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.transport.http.schemas.sse import (
    SubKaniTaskEndEventData,
    SubKaniTaskRetryEventData,
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
        and not message.tool_calls
        and message.tool_call_id is None
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
                task=task, model_id=subkani_model_id
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
                        model_id=run_state.subkani_model_id,
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
                    "data": SubKaniTaskRetryEventData(
                        task=run_state.task, attempt=attempt + 2
                    ).model_dump(by_alias=True, exclude_none=True),
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
                model_id=run_state.subkani_model_id,
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
