"""Standalone strategy editing tools (update, delete, undo) for pydantic-ai migration.

Each function takes ``RunContext[AgentDeps]`` and mirrors the original
:class:`StrategyEditOps` methods exactly.
"""

from typing import cast

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
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
from pathfinder.ai.tools.standalone.strategy_build import (
    _validate_step_parameters,
)
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import parse_op
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.domain.strategy.types import DecodedParams, DecodedParamsField
from pathfinder.integrations.veupathdb.value_decoding import encode_params
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
    step: StrategyStepNode,
    parameters: DecodedParams,
) -> ToolErrorPayload | None:
    """Validate and set parameters on a step. Returns error or None."""
    if step.secondary_input is not None:
        step.parameters = parameters
        return None
    record_type = graph.record_type or "transcript"
    try:
        canonical = await validate_parameters(
            SearchContext(site_id, record_type, step.search_name),
            parameters=parameters,
            callbacks=_make_callbacks(site_id),
        )
    except ValidationError as exc:
        return validation_error_payload(
            exc, recordType=record_type, searchName=step.search_name
        )
    step.parameters = canonical
    return None


def _validate_and_set_operator(
    step: StrategyStepNode,
    step_id: str,
    operator: str,
) -> None:
    """Validate and set operator on a binary step. Raises ModelRetry on bad input."""
    if step.secondary_input is None:
        msg = (
            f"VALIDATION_ERROR: operator can only be set for binary steps "
            f"(stepId={step_id})."
        )
        raise ModelRetry(msg)
    try:
        step.operator = parse_op(operator)
    except ValueError as exc:
        msg = (
            f"VALIDATION_ERROR: Unknown operator {operator!r} on step {step_id!r}. "
            "Use INTERSECT, UNION, MINUS, RMINUS, or COLOCATE."
        )
        raise ModelRetry(msg) from exc


async def _apply_step_updates(
    site_id: str,
    graph: StrategyGraph,
    sync_state: WDKSyncState,
    step: StrategyStepNode,
    search_name: str | None,
    parameters: DecodedParams | None,
    operator: str | None,
    display_name: str | None,
) -> ToolErrorPayload | None:
    """Apply update fields to a step. Returns an error payload or None on success."""
    substantive_change = False

    if search_name:
        step.search_name = search_name
        substantive_change = True

    if parameters is not None:
        error = await _validate_and_set_params(site_id, graph, step, parameters)
        if error is not None:
            return error
        substantive_change = True

    if operator is not None:
        _validate_and_set_operator(step, step.id, operator)
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
                    WDKSearchConfig(parameters=encode_params(step.parameters)),
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
) -> tuple[StrategyGraph, StrategyStepNode] | ToolErrorPayload:
    """Resolve graph + step and assert step is a StrategyStepNode."""
    result = get_graph_and_step(session, graph_id, step_id)
    if isinstance(result, ToolErrorPayload):
        return result
    graph, step = result
    if not isinstance(step, StrategyStepNode):
        msg = f"VALIDATION_ERROR: Unsupported step object (stepId={step_id})."
        raise ModelRetry(msg)
    return graph, step


async def update_step(
    ctx: RunContext[AgentDeps],
    step_id: str,
    search_name: str | None = None,
    parameters: DecodedParamsField | None = None,
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
        parameters: New parameter values. Use native types: list[str] for
            multi-pick, str for single-pick, dict for ranges.
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
    if parameters is not None:
        sn = search_name or step.search_name
        if sn:
            _validate_step_parameters(deps, sn, dict(parameters))

    sync_state = ensure_sync_state(session)
    apply_error = await _apply_step_updates(
        deps.site_id, graph, sync_state, step, search_name,
        dict(parameters) if parameters is not None else None,
        operator, display_name,
    )


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
        msg = (
            f"VALIDATION_ERROR: Step {step_id!r} not found in graph "
            f"{graph.id!r}. Valid step ids: {sorted(graph.steps.keys())}."
        )
        raise ModelRetry(msg)

    # Guard: refuse to delete the last step(s) — use clear_strategy instead.
    if len(graph.steps) == 1:
        msg = (
            "VALIDATION_ERROR: Deleting this step would remove all nodes. "
            "Use clear_strategy(confirm=true) to start over."
        )
        raise ModelRetry(msg)

    sync_state = ensure_sync_state(session)
    result = await delete_step_connected(graph, sync_state, step_id)


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
    msg = (
        f"VALIDATION_ERROR: Nothing to undo on graph {graph.id!r}. "
        "Make a structural change first or pick a different action."
    )
    raise ModelRetry(msg)
