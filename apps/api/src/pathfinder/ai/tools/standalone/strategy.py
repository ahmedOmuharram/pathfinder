"""Declarative strategy tools.

The execution agent's only build entry point is ``build_strategy(root)``:
it hands us a complete ``StrategyStepNode`` tree, we validate by AST
construction (the model rejects multi-root, duplicate ids, combine-with-
self, etc.), persist eagerly, and push to WDK in dependency order with
per-step retry.

After build, edits are kind-discriminated and atomic:

- ``update_leaf_params`` — leaf only, validates against the search's
  param shape, PUTs to WDK first, mutates AST on success.
- ``update_combine_operator`` — combine only, atomic.
- ``update_step_metadata`` — display name only, no WDK call.
- ``delete_step`` — preserves the single-root invariant by re-wiring
  parent to grandparent. Refuses to delete the root.
- ``replace_subtree`` — replaces the subtree at ``step_id`` with a new
  ``StrategyStepNode`` tree, atomically pushing the new subtree and
  cleaning up orphaned WDK steps.

These five edit tools are the entire post-build surface. There is no
imperative ``create_leaf_step`` / ``combine_steps`` / polymorphic
``update_step`` — the architectural shift in SC-D22 deletes them.
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
)
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.types import DecodedParamsField
from pathfinder.integrations.veupathdb.value_decoding import encode_params
from pathfinder.persistence.repositories.conversation import (
    ConversationRepository,
    ConversationUpdate,
)
from pathfinder.platform.errors import AppError, ErrorCode, ValidationError
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
from pathfinder.services.strategies.persist import (
    persist_strategy_ast_to_conversation,
)
from pathfinder.services.strategies.save_substrategy import (
    deep_clone_with_fresh_ids,
)
from pathfinder.services.strategies.spec_build import (
    BuildOutcome,
    build_strategy_from_spec,
)
from pathfinder.services.strategies.step_deletion import delete_step_connected
from pathfinder.services.strategies.sync_state import (
    WDKSyncState,
    ensure_sync_state,
)
from pathfinder.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)
from pathfinder.services.wdk import WDKSearchConfig, get_strategy_api

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


async def _push_via_search_config(
    *,
    sync_state: WDKSyncState,
    step: StrategyStepNode,
    site_id: str,
    record_type: str,
    search_name: str,
) -> str | None:
    """PUT new ``search_config`` for an already-pushed step. Returns error."""
    wdk_step_id = sync_state.wdk_step_ids.get(step.id)
    if wdk_step_id is None:
        return None
    try:
        api = get_strategy_api(site_id)
        await api.update_step_search_config(
            wdk_step_id,
            WDKSearchConfig(parameters=encode_params(step.parameters)),
            record_type=record_type,
            search_name=search_name,
        )
    except (AppError, OSError) as exc:
        logger.warning(
            "PUT search-config failed",
            step_id=step.id,
            error=str(exc),
        )
        return str(exc)
    return None


# ---------------------------------------------------------------------------
# build_strategy — declarative tree builder
# ---------------------------------------------------------------------------


async def build_strategy(
    ctx: RunContext[AgentDeps],
    root: StrategyStepNode,
    *,
    name: str | None = None,
    description: str | None = None,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject]:
    """Materialize a complete strategy from a single declarative tree.

    Pass the entire tree in one call. The AST validators reject combine-
    with-self, duplicate step ids, and other malformed shapes at
    construction time. We persist the AST eagerly, then push each step to
    WDK in DFS dependency order. Per-step push failures are recorded and
    do not abort sibling subtrees.

    Args:
        root: The root ``StrategyStepNode`` for the entire strategy.
            Combine nodes have ``primary_input`` and ``secondary_input``;
            transforms have ``primary_input`` only; leaves have neither.
        name: Optional strategy name (default: keep current graph name).
        description: Optional strategy description.
        graph_id: Target graph; uses the active graph when omitted.
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


# ---------------------------------------------------------------------------
# Edit tools — atomic, kind-discriminated
# ---------------------------------------------------------------------------


async def update_leaf_params(
    ctx: RunContext[AgentDeps],
    step_id: str,
    parameters: DecodedParamsField,
    *,
    graph_id: str | None = None,
) -> ToolReturn[StepOkResponse] | ToolErrorPayload:
    """Update a leaf step's parameters atomically.

    Validates against the search's param shape, PUTs to WDK first, only
    mutates the local AST on WDK success. A failed PUT leaves the step
    untouched — the agent gets the error and can retry with corrected
    parameters.
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
        return validation_error_payload(
            exc, recordType=record_type, searchName=step.search_name,
        )

    sync_state = ensure_sync_state(session)
    proposed = step.model_copy(update={"parameters": canonical})
    push_error = await _push_via_search_config(
        sync_state=sync_state,
        step=proposed,
        site_id=deps.site_id,
        record_type=record_type,
        search_name=step.search_name,
    )
    if push_error is not None:
        return tool_error(
            ErrorCode.WDK_ERROR,
            f"WDK rejected the parameter change: {push_error}. The local "
            "step is unchanged; fix the parameters and retry.",
            stepId=step.id,
        )

    step.parameters = canonical
    await persist_strategy_ast_to_conversation(
        deps=deps, graph=graph, sync_result=None,
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
    """Update a combine step's operator (and colocation params if COLOCATE).

    Combine-only. PUTs to WDK first, mutates local AST on success.
    """
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
        msg = (
            "VALIDATION_ERROR: COLOCATE operator requires colocation_params."
        )
        raise ModelRetry(msg)
    if operator != CombineOp.COLOCATE and colocation_params is not None:
        msg = (
            "VALIDATION_ERROR: colocation_params is only valid for COLOCATE."
        )
        raise ModelRetry(msg)

    sync_state = ensure_sync_state(session)
    proposed = step.model_copy(
        update={"operator": operator, "colocation_params": colocation_params},
    )
    record_type = graph.record_type or "transcript"
    push_error = await _push_via_search_config(
        sync_state=sync_state,
        step=proposed,
        site_id=deps.site_id,
        record_type=record_type,
        search_name=step.search_name,
    )
    if push_error is not None:
        return tool_error(
            ErrorCode.WDK_ERROR,
            f"WDK rejected the operator change: {push_error}.",
            stepId=step.id,
        )

    step.operator = operator
    step.colocation_params = colocation_params
    await persist_strategy_ast_to_conversation(
        deps=deps, graph=graph, sync_result=None,
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
    step.display_name = display_name
    await persist_strategy_ast_to_conversation(
        deps=deps, graph=graph, sync_result=None,
    )
    return ToolReturn(
        return_value=step_ok_response(session, graph, step),
        metadata=[graph_snapshot_chunk(session, graph)],
    )


async def delete_step(
    ctx: RunContext[AgentDeps],
    step_id: str,
    *,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject] | ToolErrorPayload:
    """Delete a step and re-wire the tree to preserve a single root.

    The deletion service handles parent re-wiring (parent's input slot
    moves up to the deleted step's primary input). Refuses to delete the
    root if it would leave the graph empty — use a fresh ``build_strategy``
    instead.
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
    if len(graph.steps) == 1:
        msg = (
            "VALIDATION_ERROR: Deleting this step would empty the graph. "
            "Call build_strategy with a new root to start over."
        )
        raise ModelRetry(msg)

    sync_state = ensure_sync_state(session)
    result = await delete_step_connected(graph, sync_state, step_id)
    await persist_strategy_ast_to_conversation(
        deps=deps, graph=graph, sync_result=None,
    )
    response: JSONObject = {
        "ok": True,
        "deleted": cast("JSONArray", result.deleted_ids),
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
    """Replace the subtree rooted at ``step_id`` with a new tree.

    The new subtree is validated by AST construction. Old subtree's WDK
    steps are abandoned (sync state forgets their ids); the new subtree
    is pushed via the standard build flow. The parent's input slot is
    re-wired to the new subtree's root, preserving single-root invariant.
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

    old_root_node = graph.steps[step_id]
    old_subtree_ids = {n.id for n in walk_step_tree(old_root_node)}
    parent_info = graph.find_parent(step_id)

    new_full_root = _rebuild_root_with_replacement(
        graph=graph,
        new_subtree=new_subtree,
        parent_info=parent_info,
    )

    sync_state = ensure_sync_state(session)
    for sid in old_subtree_ids:
        sync_state.wdk_step_ids.pop(sid, None)
        sync_state.wdk_push_errors.pop(sid, None)

    outcome = await build_strategy_from_spec(
        deps=deps,
        root=new_full_root,
        name=graph.name,
        description=graph.description,
    )
    payload = _build_outcome_payload(outcome, graph)
    payload["replacedStepId"] = step_id
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


async def insert_saved_strategy(
    ctx: RunContext[AgentDeps],
    target_step_id: str,
    saved_wdk_strategy_id: int,
    *,
    operator: CombineOp = CombineOp.INTERSECT,
    graph_id: str | None = None,
) -> ToolReturn[JSONObject] | ToolErrorPayload:
    """Insert a saved strategy as a new combine input next to ``target_step_id``.

    Fetches the saved WDK strategy, builds its ``StrategyStepNode`` subtree,
    deep-clones it with fresh local ids, and wraps it in a new combine step
    where ``target_step_id`` becomes the primary input and the cloned saved
    subtree becomes the secondary input. The combine carries
    ``expanded_strategy_id`` + ``expanded_name`` so the UI renders the
    secondary branch as a collapsed pill.

    The new combine slots into the parent of ``target_step_id`` (or becomes
    the new root if ``target_step_id`` was the root). The conversation's
    ``imported_saved_strategy_ids`` is amended so the saved strategy cannot
    be hard-deleted while in use.
    """
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

    api = get_strategy_api(deps.site_id)
    try:
        saved = await api.get_strategy(saved_wdk_strategy_id)
    except AppError as exc:
        return tool_error(
            ErrorCode.STRATEGY_NOT_FOUND,
            "Saved strategy not found in WDK",
            detail=(
                f"Could not load saved strategy {saved_wdk_strategy_id}: {exc}"
            ),
        )

    saved_ast = build_snapshot_from_wdk(saved)
    cloned_secondary = deep_clone_with_fresh_ids(saved_ast.root)

    target_node = graph.steps[target_step_id]
    parent_info = graph.find_parent(target_step_id)
    new_combine = StrategyStepNode(
        search_name="__combine__",
        operator=operator,
        primary_input=target_node,
        secondary_input=cloned_secondary,
        expanded_strategy_id=saved_wdk_strategy_id,
        expanded_name=saved.name or f"Saved strategy {saved_wdk_strategy_id}",
    )
    new_full_root = _rebuild_root_with_replacement(
        graph=graph,
        new_subtree=new_combine,
        parent_info=parent_info,
    )

    outcome = await build_strategy_from_spec(
        deps=deps,
        root=new_full_root,
        name=graph.name,
        description=graph.description,
    )

    await _record_saved_strategy_consumer(
        deps=deps,
        wdk_strategy_id=saved_wdk_strategy_id,
    )

    payload = _build_outcome_payload(outcome, graph)
    payload["insertedSavedStrategyId"] = saved_wdk_strategy_id
    payload["insertedSavedStrategyName"] = saved.name
    payload["combineStepId"] = new_combine.id
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


async def _record_saved_strategy_consumer(
    *,
    deps: AgentDeps,
    wdk_strategy_id: int,
) -> None:
    """Append ``wdk_strategy_id`` to the conversation's consumer list."""
    if deps.conversation_id is None or deps.db_session_factory is None:
        return
    async with deps.db_session_factory() as session:
        repo = ConversationRepository(session)
        conv = await repo.get_by_id(deps.conversation_id)
        if conv is None:
            return
        existing = list(conv.imported_saved_strategy_ids or [])
        if wdk_strategy_id in existing:
            return
        existing.append(wdk_strategy_id)
        await repo.update_conversation(
            conv.id,
            ConversationUpdate(imported_saved_strategy_ids=existing),
        )
        await session.commit()


def _swap_input(
    parent: StrategyStepNode,
    slot: str,
    replacement: StrategyStepNode,
) -> StrategyStepNode:
    field = "primary_input" if slot == "primary" else "secondary_input"
    return parent.model_copy(update={field: replacement})


def _rebuild_root_with_replacement(
    *,
    graph: StrategyGraph,
    new_subtree: StrategyStepNode,
    parent_info: tuple[StrategyStepNode, str] | None,
) -> StrategyStepNode:
    """Walk up to the graph root, rebuilding parents to point at the new subtree."""
    if parent_info is None:
        return new_subtree
    parent, slot = parent_info
    current = _swap_input(parent, slot, new_subtree)
    while True:
        up = graph.find_parent(current.id)
        if up is None:
            return current
        up_parent, up_slot = up
        current = _swap_input(up_parent, up_slot, current)
