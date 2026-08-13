"""Declarative strategy tools for the execution agent.

A build takes one complete step tree. Every later edit builds a graph
operation and applies it through the single commit path.
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
from pathfinder.domain.strategy.graph_model import StepKind
from pathfinder.domain.strategy.operations import (
    DeleteResolution,
    DeleteStepOp,
    GraphOperation,
    ReplaceSubtreeOp,
    UpdateCombineOperatorOp,
    UpdateStepMetaOp,
    UpdateStepParamsOp,
)
from pathfinder.domain.strategy.operations.apply import ApplyError
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp
from pathfinder.domain.strategy.revision import strategy_revision
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
from pathfinder.services.strategies.commit import (
    apply_and_commit,
    apply_operations_and_commit,
)
from pathfinder.services.strategies.insert_saved import (
    insert_saved_into_conversation,
)
from pathfinder.services.strategies.spec_build import build_strategy_from_spec

logger = get_logger(__name__)


def _make_callbacks(site_id: str) -> ValidationCallbacks:
    return make_validation_callbacks(site_id, error_payload=validation_error_payload)


def _build_outcome_payload(outcome: BuildOutcome, graph: StrategyGraph) -> JSONObject:
    """Serializes a build outcome into the tool response payload."""
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
    base_revision: str | None = None,
) -> ToolReturn[JSONObject]:
    """Materialize a complete strategy from a single declarative tree.

    Use this to build a strategy from nothing. To CHANGE a strategy that
    already exists, use `apply_operations` instead -- this replaces the whole
    graph, so it costs the entire strategy in tokens and overwrites anything
    the researcher edited in the meantime.

    Replacing a non-empty strategy requires `base_revision` (the `revision`
    from `get_strategy`), so a replacement is always something you chose
    rather than something that happened.

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

    current = _current_revision(graph)
    if current and base_revision != current:
        msg = (
            f"CONFLICT: this strategy already has {len(graph.steps)} step(s), and "
            f"build_strategy replaces all of them. If you meant to change it, "
            f"call apply_operations with base_revision={current!r} and send only "
            f"the edits. If you really do mean to replace the whole strategy, "
            f"re-call build_strategy with base_revision={current!r}."
        )
        raise ModelRetry(msg)

    outcome = await build_strategy_from_spec(
        deps=deps.to_strategy_context(),
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


def _current_revision(graph: StrategyGraph) -> str:
    return strategy_revision(graph.to_strategy_ast())


async def apply_operations(
    ctx: RunContext[AgentDeps],
    base_revision: str,
    operations: list[GraphOperation],
    graph_id: str | None = None,
) -> ToolReturn[JSONObject]:
    """Edit the strategy with a batch of operations, not a whole new tree.

    Prefer this over `build_strategy` for any change to a strategy that
    already exists: it sends only what changes, so adding one step does not
    mean restating every existing step's parameters.

    `base_revision` is the `revision` from the most recent `get_strategy`.
    If the strategy changed since then -- typically because the researcher
    edited a parameter in the UI -- nothing is applied and you are told the
    current revision, so you can re-read and decide whether your edit still
    makes sense. Use `""` for a strategy that does not exist yet.

    Operations apply in order and all land together; if one is rejected the
    strategy is left exactly as it was.
    """
    deps = ctx.deps
    session = deps.strategy_session
    graph = get_graph(session, graph_id)
    if graph is None:
        return ToolReturn(
            return_value=cast("JSONObject", graph_not_found(graph_id)),
        )

    if not operations:
        msg = (
            "VALIDATION_ERROR: apply_operations needs at least one operation. "
            "Pass the edits you want to make, or call get_strategy to look first."
        )
        raise ModelRetry(msg)

    current = _current_revision(graph)
    if base_revision != current:
        msg = (
            f"CONFLICT: the strategy changed since you last read it "
            f"(you passed base_revision={base_revision!r}, current is "
            f"{current!r}). Nothing was applied. Call get_strategy to see the "
            f"current state, then re-issue only the edits that still apply -- "
            f"the researcher may have already made this change themselves."
        )
        raise ModelRetry(msg)

    try:
        result = await apply_operations_and_commit(
            deps=deps.to_strategy_context(),
            ops=operations,
        )
    except ApplyError as exc:
        # A rejected batch rolls back, so the base revision stays valid.
        msg = (
            f"REJECTED: {exc}. Nothing was applied and the strategy is "
            f"unchanged, so base_revision={current!r} is still valid. Fix the "
            f"offending operation and send the batch again."
        )
        raise ModelRetry(msg) from exc
    payload: JSONObject = {
        "applied": len(operations),
        "description": result.description,
        "droppedStepIds": cast("JSONArray", list(result.dropped_step_ids)),
        "revision": _current_revision(graph),
    }
    return ToolReturn(
        return_value=payload,
        metadata=[graph_snapshot_chunk(session, graph)],
    )


async def update_leaf_params(
    ctx: RunContext[AgentDeps],
    step_id: str,
    parameters: dict[str, ParamValue],
    *,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Update a leaf step's parameters — a partial patch.

    Only the params you pass are changed; the step's other params are kept, so
    you can update one param without re-supplying the whole search config. Each
    value MUST be wrapped in its typed shape — see the ``valueFormat`` field
    from ``get_search_overview`` for the exact template per param. Example:
    ``{"organism": {"type": "multi-pick-vocabulary", "values": ["Pf3D7"]}}``.
    """
    deps = ctx.deps
    session = deps.strategy_session
    resolved = get_graph_and_step(session, graph_id, step_id)
    if isinstance(resolved, ToolErrorPayload):
        return resolved
    graph, step = resolved

    if step.kind is not StepKind.SEARCH:
        msg = (
            f"VALIDATION_ERROR: update_leaf_params only applies to leaf "
            f"steps; step {step_id!r} is a "
            f"{step.kind.value}. Use update_combine_operator (combine) "
            f"or replace_subtree to change a non-leaf step."
        )
        raise ModelRetry(msg)

    record_type = graph.record_type or "transcript"
    merged = {**step.parameters, **parameters}
    try:
        canonical = await validate_parameters(
            SearchContext(deps.site_id, record_type, step.search_name or ""),
            parameters=merged,
            callbacks=_make_callbacks(deps.site_id),
        )
    except ValidationError as exc:
        raise validation_model_retry(
            exc,
            recordType=record_type,
            searchName=step.search_name,
        ) from exc

    await apply_and_commit(
        deps=deps.to_strategy_context(),
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

    if step.kind is not StepKind.COMBINE:
        msg = (
            f"VALIDATION_ERROR: update_combine_operator only applies to "
            f"combine steps; step {step_id!r} is a {step.kind.value}."
        )
        raise ModelRetry(msg)

    if operator == CombineOp.COLOCATE and colocation_params is None:
        msg = "VALIDATION_ERROR: COLOCATE operator requires colocation_params."
        raise ModelRetry(msg)
    if operator != CombineOp.COLOCATE and colocation_params is not None:
        msg = "VALIDATION_ERROR: colocation_params is only valid for COLOCATE."
        raise ModelRetry(msg)

    await apply_and_commit(
        deps=deps.to_strategy_context(),
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
        deps=deps.to_strategy_context(),
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
        deps=deps.to_strategy_context(),
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
        deps=deps.to_strategy_context(),
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
