"""Standalone strategy editing tools (update, delete, undo) for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
:class:`StrategyEditOps` methods exactly.
"""

from collections.abc import Mapping
from typing import cast

from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._graph_helpers import (
    step_ok_response,
    with_full_graph,
)
from pathfinder.ai.tools.standalone._record_type_helpers import (
    find_record_type_for_search,
    find_record_type_hint,
)
from pathfinder.ai.tools.standalone._stream_parts import (
    graph_snapshot_chunk,
    strategy_patch_chunk,
    strategy_remove_chunk,
)
from pathfinder.ai.tools.standalone._validation_helpers import (
    StepOkResponse,
    get_graph,
    get_graph_and_step,
    graph_not_found,
    validation_error_payload,
)
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.ops import parse_op
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.domain.strategy.types import SerializedParams
from pathfinder.platform.errors import AppError, ErrorCode, ValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONArray, JSONObject
from pathfinder.services.catalog.param_validation import (
    ValidationCallbacks,
    validate_parameters,
)
from pathfinder.services.strategies.step_deletion import delete_step_connected
from pathfinder.services.strategies.sync_state import WDKSyncState, ensure_sync_state
from pathfinder.services.wdk import WDKSearchConfig, get_strategy_api

logger = get_logger(__name__)


def _make_callbacks(site_id: str) -> ValidationCallbacks:
    """Build validation callbacks bound to the given site."""

    async def _resolve(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = True,
    ) -> str | None:
        return await find_record_type_for_search(
            site_id,
            record_type,
            search_name,
            require_match=require_match,
            allow_fallback=allow_fallback,
        )

    async def _hint(search_name: str, exclude: str | None = None) -> str | None:
        return await find_record_type_hint(site_id, search_name, exclude)

    return ValidationCallbacks(
        resolve_record_type_for_search=_resolve,
        find_record_type_hint=_hint,
    )


async def _validate_and_set_params(
    site_id: str,
    graph: StrategyGraph,
    step: PlanStepNode,
    parameters: JSONObject,
) -> ToolErrorPayload | None:
    """Validate and set parameters on a step. Returns error or None."""
    wdk_params = cast("dict[str, str]", parameters)
    if step.secondary_input is not None:
        step.parameters = wdk_params
        return None
    record_type = graph.record_type or "transcript"
    try:
        await validate_parameters(
            SearchContext(site_id, record_type, step.search_name),
            parameters=parameters,
            callbacks=_make_callbacks(site_id),
        )
    except ValidationError as exc:
        return validation_error_payload(
            exc, recordType=record_type, searchName=step.search_name
        )
    step.parameters = wdk_params
    return None


def _validate_and_set_operator(
    step: PlanStepNode,
    step_id: str,
    operator: str,
) -> ToolErrorPayload | None:
    """Validate and set operator on a binary step. Returns error or None."""
    if step.secondary_input is None:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "operator can only be set for binary steps.",
            stepId=step_id,
        )
    try:
        step.operator = parse_op(operator)
    except ValueError:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            f"Unknown operator: {operator}",
            stepId=step_id,
        )
    return None


async def _apply_step_updates(
    site_id: str,
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    step: PlanStepNode,
    search_name: str | None,
    parameters: Mapping[str, str] | JSONObject | None,
    operator: str | None,
    display_name: str | None,
) -> ToolErrorPayload | None:
    """Apply update fields to a step. Returns an error payload or None on success."""
    substantive_change = False

    if search_name:
        step.search_name = search_name
        substantive_change = True

    if parameters is not None:
        params_dict: JSONObject = dict(parameters)
        error = await _validate_and_set_params(site_id, graph, step, params_dict)
        if error is not None:
            return error
        substantive_change = True

    if operator is not None:
        error = _validate_and_set_operator(step, step.id, operator)
        if error is not None:
            return error
        substantive_change = True

    if display_name:
        step.display_name = display_name

    if substantive_change:
        wdk_step_id = sync_state.wdk_step_ids.get(step.id)
        if wdk_step_id is not None and parameters is not None:
            try:
                api = get_strategy_api(graph.site_id)
                await api.update_step_search_config(
                    wdk_step_id,
                    WDKSearchConfig(
                        parameters={
                            k: str(v)
                            for k, v in step.parameters.items()
                            if v is not None
                        },
                    ),
                    record_type=graph.record_type or "transcript",
                    search_name=step.search_name,
                )
            except (AppError, OSError) as exc:
                logger.warning(
                    "PUT search-config failed",
                    step_id=step.id,
                    error=str(exc),
                )
                sync_state.wdk_push_errors[step.id] = str(exc)
                return tool_error(
                    ErrorCode.WDK_ERROR,
                    f"Local step updated but WDK rejected the change: {exc}. "
                    f"The next auto-build will retry with the corrected parameters.",
                    stepId=step.id,
                    wdkStepId=wdk_step_id,
                )

    return None


def _get_plan_step(
    session: StrategySession,
    graph_id: str | None,
    step_id: str,
) -> tuple[StrategyGraph, PlanStepNode] | ToolErrorPayload:
    """Resolve graph + step and assert step is a PlanStepNode."""
    result = get_graph_and_step(session, graph_id, step_id)
    if isinstance(result, ToolErrorPayload):
        return result
    graph, step = result
    if not isinstance(step, PlanStepNode):
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Unsupported step object.",
            stepId=step_id,
        )
    return graph, step


async def update_step(
    ctx: RunContext[AgentDeps],
    step_id: str,
    search_name: str | None = None,
    parameters: SerializedParams | None = None,
    operator: str | None = None,
    display_name: str | None = None,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Update an existing strategy step's search, parameters, operator, or display name.

    Parameter changes are synced to WDK immediately via PUT search-config.
    If the WDK push fails the local step is still updated and the next
    auto-build will retry.

    Args:
        step_id: ID of the step to update.
        search_name: New WDK search urlSegment. Replaces the current search.
        parameters: New parameter values (paramName -> value string). Merged into WDK.
        operator: New set operator for binary steps (INTERSECT, UNION, MINUS, RMINUS).
        display_name: New human-readable label shown in the UI.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    resolved = _get_plan_step(session, graph_id, step_id)
    if isinstance(resolved, ToolErrorPayload):
        return resolved
    graph, step = resolved

    sync_state = ensure_sync_state(session)
    apply_error = await _apply_step_updates(
        deps.site_id, graph, sync_state, step, search_name, parameters, operator, display_name
    )

    deps.tool_repetition_guard.record_modifying_call("update_step")

    if apply_error is not None:
        return apply_error
    return ToolReturn(
        return_value=step_ok_response(session, graph, step),
        metadata=[
            graph_snapshot_chunk(session, graph),
            strategy_patch_chunk(
                graph, step,
                operation="update_step",
                sync_state=sync_state,
            ),
        ],
    )


async def delete_step(
    ctx: RunContext[AgentDeps],
    step_id: str,
    graph_id: str | None = None,
) -> ToolErrorPayload | ToolReturn[JSONObject]:
    """Delete a step and re-wire connections so the graph stays valid.

    Cannot delete the last step -- use clear_strategy instead.

    Args:
        step_id: ID of the step to delete.
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)

    if step_id not in graph.steps:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            f"Step '{step_id}' not found.",
            graphId=graph.id,
        )

    # Guard: refuse to delete the last step(s) — use clear_strategy instead.
    if len(graph.steps) == 1:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "Deleting this step would remove all nodes. Use clear_strategy(confirm=true) to start over.",
            graphId=graph.id,
            requiresConfirmation=True,
        )

    sync_state = ensure_sync_state(session)
    result = await delete_step_connected(graph, sync_state, step_id)

    deps.tool_repetition_guard.record_modifying_call("delete_step")

    response: JSONObject = {
        "deleted": cast("JSONArray", result.deleted_ids),
        "graphId": graph.id,
    }
    # One data-strategy-update per removed step; one graph-snapshot for the new state.
    metadata = [graph_snapshot_chunk(session, graph)]
    metadata.extend(strategy_remove_chunk(graph, sid) for sid in result.deleted_ids)
    return ToolReturn(
        return_value=with_full_graph(session, graph, response),
        metadata=metadata,
    )


async def undo_last_change(
    ctx: RunContext[AgentDeps],
    graph_id: str | None = None,
) -> ToolErrorPayload | ToolReturn[JSONObject]:
    """Undo the last change to the strategy.

    Only one level of undo. Reverts the last structural change
    (creation, deletion, reconnection).

    Args:
        graph_id: Target graph. Uses the active graph if omitted.
    """
    deps = ctx.deps
    session = deps.strategy_session

    graph = get_graph(session, graph_id)
    if not graph:
        return graph_not_found(graph_id)
    if graph.undo():
        return ToolReturn(
            return_value=with_full_graph(
                session,
                graph,
                {
                    "ok": True,
                    "graphId": graph.id,
                    "message": "Undone to previous state",
                },
            ),
            metadata=[graph_snapshot_chunk(session, graph)],
        )
    return ToolReturn(
        return_value=with_full_graph(
            session,
            graph,
            tool_error(
                ErrorCode.VALIDATION_ERROR, "Nothing to undo", graphId=graph.id
            ).model_dump(by_alias=True, exclude_none=True, mode="json"),
        ),
        metadata=[graph_snapshot_chunk(session, graph)],
    )
