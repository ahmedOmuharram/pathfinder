"""Declarative strategy tools.

The execution agent's only build entry point is ``build_strategy(root)``:
it hands us a complete ``StrategyStepNode`` tree, we validate by AST
construction (the model rejects multi-root, duplicate ids, combine-with-
self, etc.), persist eagerly, and push to WDK in dependency order with
per-step retry.

After build, edits are kind-discriminated and atomic. Every edit tool is
a thin wrapper that builds a ``GraphOperation`` and forwards to
``apply_and_commit`` — a single chokepoint that owns persist + WDK push +
WDK step cleanup + sync + history.
"""

from __future__ import annotations

from typing import cast

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._graph_helpers import (
    step_ok_response,
    with_full_graph,
)
from pathfinder.ai.tools.standalone._stream_parts import (
    graph_snapshot_chunk,
    strategy_link_chunk,
)
from pathfinder.ai.tools.standalone._validation_helpers import (
    StepOkResponse,
    get_graph,
    get_graph_and_step,
    graph_not_found,
    validation_error_payload,
    validation_model_retry,
)
from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.operations import (
    DeleteResolution,
    DeleteStepOp,
    ReplaceSubtreeOp,
    UpdateCombineOperatorOp,
    UpdateStepMetaOp,
    UpdateStepParamsOp,
)
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.errors import ErrorCode, ValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONArray, JSONObject
from pathfinder.services.catalog.param_validation import (
    ValidationCallbacks,
    validate_parameters,
)
from pathfinder.services.catalog.validation_callbacks import (
    make_validation_callbacks,
)
from pathfinder.services.strategies.commit import apply_and_commit
from pathfinder.services.strategies.insert_saved import (
    insert_saved_into_conversation,
)
from pathfinder.services.strategies.spec_build import build_strategy_from_spec

logger = get_logger(__name__)


def _make_callbacks(site_id: str) -> ValidationCallbacks:
    return make_validation_callbacks(site_id, error_payload=validation_error_payload)


def _build_outcome_payload(outcome: BuildOutcome, graph: StrategyGraph) -> JSONObject:
    """Serialize a ``BuildOutcome`` to the LLM-facing response payload."""
    payload: JSONObject = {
        "ok": outcome.fully_succeeded,
        "wdkStrategyId": outcome.wdk_strategy_id,
        "wdkUrl": outcome.wdk_url,
        "rootCount": outcome.root_count,
        "stepCount": len(graph.steps),
        "pushedStepIds": cast("JSONArray", outcome.pushed_step_ids),
        "failedSteps": cast(
            "JSONArray",
            [
                {
                    "stepId": f.step_id,
                    "searchName": f.search_name,
                    "error": f.error,
                }
                for f in outcome.failed_steps
            ],
        ),
        "skippedStepIds": cast("JSONArray", outcome.skipped_step_ids),
        "zeroStepIds": cast("JSONArray", outcome.zero_step_ids),
        "counts": cast("JSONObject", dict(outcome.counts)),
    }
    if outcome.failed_steps:
        payload["hint"] = (
            "Some steps failed to push to WDK. Local AST is intact — use "
            "update_leaf_params to fix the failed step's parameters, or "
            "delete_step / replace_subtree to restructure. The build will "
            "retry on next mutation."
        )
    return payload


async def build_strategy(
    ctx: RunContext[AgentDeps],
    root: StrategyStepNode,
    *,
    name: str | None = None,
    description: str | None = None,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject]:
    """Materialize a complete strategy from a single declarative tree.

    The ENTIRE strategy is passed as a single `root` argument — a recursive
    StrategyStepNode where every combine has its inputs nested inside it.
    Do NOT put `primaryInput`, `secondaryInput`, `searchName`, or
    `parameters` at the top level of the tool args — they ONLY exist
    inside `root` (and inside nodes within `root`).

    Example — INTERSECT(UNION(A, B), C) where A, B, C are leaf searches:

        build_strategy(
            root={
                "operator": "INTERSECT",
                "primaryInput": {
                    "operator": "UNION",
                    "primaryInput":   {"searchName": "A", "parameters": {...}},
                    "secondaryInput": {"searchName": "B", "parameters": {...}},
                },
                "secondaryInput": {"searchName": "C", "parameters": {...}},
            },
            name="...",
        )

    To add a NEW set as a sibling of an existing tree, wrap the existing
    tree in a new combine: the existing tree becomes `primaryInput`, the
    new set becomes `secondaryInput`, and the new combine replaces `root`.
    """
    deps = ctx.deps
    session = deps.strategy_session
    graph = get_graph(session, graph_id)
    if graph is None:
        return ToolReturn(
            return_value=cast("JSONObject", graph_not_found(graph_id)),
        )

    outcome = await build_strategy_from_spec(
        deps=deps,
        root=root,
        name=name,
        description=description,
    )
    payload = _build_outcome_payload(outcome, graph)
    metadata = [graph_snapshot_chunk(session, graph)]
    if outcome.wdk_url is not None:
        metadata.append(
            strategy_link_chunk(
                strategy_id=graph.id,
                url=outcome.wdk_url,
                title=graph.name,
            ),
        )
    return ToolReturn(return_value=payload, metadata=metadata)


async def update_leaf_params(
    ctx: RunContext[AgentDeps],
    step_id: str,
    parameters: dict[str, ParamValue],
    *,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Update a leaf step's parameters atomically.

    Each value in ``parameters`` MUST be wrapped in its typed shape — see
    the ``valueFormat`` field from ``get_search_overview`` for the exact
    template per param. Example:
    ``{"organism": {"type": "multi-pick-vocabulary", "values": ["Pf3D7"]}}``.
    """
    deps = ctx.deps
    session = deps.strategy_session
    resolved = get_graph_and_step(session, graph_id, step_id)
    if isinstance(resolved, ToolErrorPayload):
        return resolved
    graph, step = resolved

    if step.primary_input is not None or step.secondary_input is not None:
        msg = (
            f"VALIDATION_ERROR: update_leaf_params only applies to leaf "
            f"steps; step {step_id!r} is a "
            f"{step.infer_kind()}. Use update_combine_operator (combine) "
            f"or replace_subtree to change a non-leaf step."
        )
        raise ModelRetry(msg)

    record_type = graph.record_type or "transcript"
    try:
        canonical = await validate_parameters(
            SearchContext(deps.site_id, record_type, step.search_name),
            parameters=dict(parameters),
            callbacks=_make_callbacks(deps.site_id),
        )
    except ValidationError as exc:
        raise validation_model_retry(
            exc, recordType=record_type, searchName=step.search_name,
        ) from exc

    await apply_and_commit(
        deps=deps,
        op=UpdateStepParamsOp(step_id=step_id, parameters=dict(canonical)),
    )
    return ToolReturn(
        return_value=step_ok_response(session, graph, step),
        metadata=[graph_snapshot_chunk(session, graph)],
    )


async def update_combine_operator(
    ctx: RunContext[AgentDeps],
    step_id: str,
    operator: CombineOp,
    colocation_params: ColocationParams | None = None,
    *,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Update a combine step's operator (and colocation params if COLOCATE)."""
    deps = ctx.deps
    session = deps.strategy_session
    resolved = get_graph_and_step(session, graph_id, step_id)
    if isinstance(resolved, ToolErrorPayload):
        return resolved
    graph, step = resolved

    if step.primary_input is None or step.secondary_input is None:
        msg = (
            f"VALIDATION_ERROR: update_combine_operator only applies to "
            f"combine steps; step {step_id!r} is a {step.infer_kind()}."
        )
        raise ModelRetry(msg)

    if operator == CombineOp.COLOCATE and colocation_params is None:
        msg = "VALIDATION_ERROR: COLOCATE operator requires colocation_params."
        raise ModelRetry(msg)
    if operator != CombineOp.COLOCATE and colocation_params is not None:
        msg = "VALIDATION_ERROR: colocation_params is only valid for COLOCATE."
        raise ModelRetry(msg)

    await apply_and_commit(
        deps=deps,
        op=UpdateCombineOperatorOp(
            step_id=step_id,
            operator=operator,
            colocation_params=colocation_params,
        ),
    )
    return ToolReturn(
        return_value=step_ok_response(session, graph, step),
        metadata=[graph_snapshot_chunk(session, graph)],
    )


async def update_step_metadata(
    ctx: RunContext[AgentDeps],
    step_id: str,
    display_name: str,
    *,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Update a step's display name. Local-only — no WDK call."""
    deps = ctx.deps
    session = deps.strategy_session
    resolved = get_graph_and_step(session, graph_id, step_id)
    if isinstance(resolved, ToolErrorPayload):
        return resolved
    graph, step = resolved

    await apply_and_commit(
        deps=deps,
        op=UpdateStepMetaOp(step_id=step_id, display_name=display_name),
    )
    return ToolReturn(
        return_value=step_ok_response(session, graph, step),
        metadata=[graph_snapshot_chunk(session, graph)],
    )


async def delete_step(
    ctx: RunContext[AgentDeps],
    step_id: str,
    *,
    resolution: DeleteResolution = DeleteResolution.COLLAPSE_COMBINE,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject] | ToolErrorPayload:
    """Delete a step and re-wire the tree to preserve a single root.

    ``resolution`` selects the disambiguation policy. Defaults to
    ``collapse-combine`` which drops the step + its parent combine and
    reconnects the sibling to the grandparent.
    """
    deps = ctx.deps
    session = deps.strategy_session
    graph = get_graph(session, graph_id)
    if graph is None:
        return graph_not_found(graph_id)
    if step_id not in graph.steps:
        msg = (
            f"VALIDATION_ERROR: Step {step_id!r} not found. Valid step "
            f"ids: {sorted(graph.steps.keys())}."
        )
        raise ModelRetry(msg)

    result = await apply_and_commit(
        deps=deps,
        op=DeleteStepOp(step_id=step_id, resolution=resolution),
    )
    response: JSONObject = {
        "ok": True,
        "deleted": cast("JSONArray", result.dropped_step_ids),
        "graphId": graph.id,
    }
    return ToolReturn(
        return_value=with_full_graph(session, graph, response),
        metadata=[graph_snapshot_chunk(session, graph)],
    )


async def replace_subtree(
    ctx: RunContext[AgentDeps],
    step_id: str,
    new_subtree: StrategyStepNode,
    *,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject] | ToolErrorPayload:
    """Replace the subtree rooted at ``step_id`` with a new tree."""
    deps = ctx.deps
    session = deps.strategy_session
    graph = get_graph(session, graph_id)
    if graph is None:
        return graph_not_found(graph_id)
    if step_id not in graph.steps:
        msg = (
            f"VALIDATION_ERROR: Step {step_id!r} not found. Valid step "
            f"ids: {sorted(graph.steps.keys())}."
        )
        raise ModelRetry(msg)

    result = await apply_and_commit(
        deps=deps,
        op=ReplaceSubtreeOp(step_id=step_id, subtree=new_subtree),
    )
    payload: JSONObject = {
        "ok": True,
        "replacedStepId": step_id,
        "droppedStepIds": cast("JSONArray", result.dropped_step_ids),
        "graphId": graph.id,
    }
    metadata = [graph_snapshot_chunk(session, graph)]
    sync_result = result.sync_result
    if sync_result is not None and sync_result.wdk_url is not None:
        metadata.append(
            strategy_link_chunk(
                strategy_id=graph.id,
                url=sync_result.wdk_url,
                title=graph.name,
            ),
        )
    return ToolReturn(
        return_value=with_full_graph(session, graph, payload),
        metadata=metadata,
    )


async def insert_saved_strategy(
    ctx: RunContext[AgentDeps],
    target_step_id: str,
    saved_wdk_strategy_id: int,
    *,
    operator: CombineOp = CombineOp.INTERSECT,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject] | ToolErrorPayload:
    """Insert a saved WDK strategy as a new combine input next to ``target_step_id``."""
    deps = ctx.deps
    session = deps.strategy_session
    graph = get_graph(session, graph_id)
    if graph is None:
        return graph_not_found(graph_id)
    if target_step_id not in graph.steps:
        msg = (
            f"VALIDATION_ERROR: Step {target_step_id!r} not found. Valid "
            f"step ids: {sorted(graph.steps.keys())}."
        )
        raise ModelRetry(msg)

    if deps.conversation_id is None or deps.db_session_factory is None:
        return tool_error(
            ErrorCode.INTERNAL_ERROR,
            "insert_saved_strategy requires a persistent conversation context",
        )

    result = await insert_saved_into_conversation(
        session=session,
        site_id=deps.site_id,
        conversation_id=deps.conversation_id,
        db_session_factory=deps.db_session_factory,
        target_step_id=target_step_id,
        saved_wdk_strategy_id=saved_wdk_strategy_id,
        operator=operator,
    )

    payload: JSONObject = {
        "ok": True,
        "insertedSavedStrategyId": result.inserted_saved_wdk_strategy_id,
        "insertedSavedStrategyName": result.inserted_saved_name,
        "combineStepId": result.combine_step_id,
        "wdkStrategyId": result.wdk_strategy_id,
        "graphId": graph.id,
    }
    return ToolReturn(
        return_value=with_full_graph(session, graph, payload),
        metadata=[graph_snapshot_chunk(session, graph)],
    )
