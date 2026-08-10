"""Atomic strategy build from a declarative ``StrategyStepNode`` tree.

The build flow:

1. The agent (or any caller) hands us a complete ``StrategyStepNode`` tree.
2. We replace the graph's contents with the tree's nodes (depth-first walk).
3. We persist ``strategy_ast`` to the conversation row immediately — no
   gating on multi-root, no waiting for WDK. Local truth is committed.
4. We push each step to WDK in dependency order (leaves → transforms →
   combines). Failures are recorded per-step in ``sync_state`` and do not
   abort the build; siblings/descendants of failed nodes are skipped.
5. After all pushes, we run ``sync_strategy_for_site`` to materialize the
   WDK strategy + persist the resulting ``wdk_strategy_id`` and counts.

This is the single entry point for declarative strategy construction. The
imperative tools (create_leaf_step, combine_steps, update_step) that
mutate the graph one operation at a time and rely on the auto-build hook
are deleted in the same change set.
"""

from __future__ import annotations

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
)
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
    NodeResult,
    StepPushFailure,
    node_status,
)
from pathfinder.domain.strategy.graph_model import (
    StrategyStep,
    flatten_tree,
    subtree_ids,
    wdk_search_name,
)
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.platform.errors import AppError, ValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.services.catalog.param_validation import validate_parameters
from pathfinder.services.catalog.validation_callbacks import (
    make_validation_callbacks,
)
from pathfinder.services.strategies.context import StrategyMutationContext
from pathfinder.services.strategies.persist import (
    persist_strategy_ast_to_conversation,
)
from pathfinder.services.strategies.reconcile import reconcile_sync_state_with_wdk
from pathfinder.services.strategies.step_wdk_push import push_step_to_wdk
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import WDKSyncState, ensure_sync_state

logger = get_logger(__name__)


def _node_results(
    nodes: list[StrategyStep],
    sync_state: WDKSyncState,
    outcome: BuildOutcome,
) -> list[NodeResult]:
    failed = {f.step_id: f.error for f in outcome.failed_steps}
    return [
        NodeResult(
            node_id=node.id,
            search_name=node.search_name or COMBINE_SEARCH_NAME,
            wdk_step_id=sync_state.wdk_step_ids.get(node.id),
            count=outcome.counts.get(node.id),
            status=node_status(
                count=outcome.counts.get(node.id), failed=node.id in failed
            ),
            error=failed.get(node.id),
        )
        for node in nodes
    ]


def _replace_graph_contents(
    graph: StrategyGraph,
    root: StrategyStepNode,
    *,
    name: str | None,
    description: str | None,
) -> None:
    """Swap the graph for the spec's tree, keeping the old one undoable.

    Materializing a spec is meant to replace what is there, so this stays
    destructive. But the Lead may rebuild on a later turn - its own rule is
    "not again unless the user changes the goal" - and by then the researcher
    may have corrected a parameter by hand. Snapshotting first is what leaves
    them a way back.
    """
    if graph.steps:
        graph.save_history("Replaced by the operational spec")

    graph.steps = flatten_tree(root)
    graph.recompute_roots()
    graph.last_step_id = root.id
    if name is not None:
        graph.name = name
    if description is not None:
        graph.description = description


async def build_strategy_from_spec(
    *,
    deps: StrategyMutationContext,
    root: StrategyStepNode,
    name: str | None = None,
    description: str | None = None,
) -> BuildOutcome:
    """Materialize a declarative tree into the graph + WDK + persistence.

    Replaces the active graph's contents with ``root`` and its descendants,
    persists the full AST to the conversation row, then pushes each step
    to WDK in DFS dependency order. Per-step failures are recorded but do
    not abort the build — sibling subtrees still attempt their pushes.
    """
    session = deps.strategy_session
    graph = session.get_graph(None)
    if graph is None:
        msg = "no active strategy graph for the current conversation"
        raise RuntimeError(msg)

    steps_by_id = flatten_tree(root)
    nodes = [steps_by_id[sid] for sid in subtree_ids(root.id, steps_by_id)]
    _replace_graph_contents(graph, root, name=name, description=description)

    sync_state = ensure_sync_state(session)
    await reconcile_sync_state_with_wdk(
        sync_state,
        deps.site_id,
        sync_state.wdk_strategy_id,
    )

    # Persist the local AST immediately so the rail reflects the agent's
    # declared structure even if WDK pushes fail or take time.
    await persist_strategy_ast_to_conversation(
        deps=deps,
        graph=graph,
        sync_result=None,
    )

    outcome = BuildOutcome()
    await _push_tree_to_wdk(
        nodes=nodes,
        graph_record_type=graph.record_type or "transcript",
        site_id=deps.site_id,
        sync_state=sync_state,
        outcome=outcome,
    )

    if outcome.failed_steps or outcome.skipped_step_ids:
        # Re-persist with the wdk_step_ids that did land. No sync (a sync
        # call would raise on the unpushed steps).
        await persist_strategy_ast_to_conversation(
            deps=deps,
            graph=graph,
            sync_result=None,
        )
        outcome.node_results = _node_results(nodes, sync_state, outcome)
        return outcome

    try:
        sync_result = await sync_strategy_for_site(
            graph=graph,
            sync_state=sync_state,
            site_id=deps.site_id,
            strategy_name=graph.name,
        )
    except AppError as exc:
        logger.warning("strategy sync failed", error=str(exc))
        await persist_strategy_ast_to_conversation(
            deps=deps,
            graph=graph,
            sync_result=None,
        )
        outcome.failed_steps.append(
            StepPushFailure(
                step_id=root.id,
                search_name=root.search_name,
                error=str(exc),
            ),
        )
        outcome.node_results = _node_results(nodes, sync_state, outcome)
        return outcome

    outcome.wdk_strategy_id = sync_result.wdk_strategy_id
    outcome.wdk_url = sync_result.wdk_url
    outcome.counts = {str(k): v for k, v in sync_result.counts.items()}
    outcome.root_count = sync_result.root_count
    outcome.zero_step_ids = list(sync_result.zero_step_ids)

    outcome.node_results = _node_results(nodes, sync_state, outcome)
    await persist_strategy_ast_to_conversation(
        deps=deps,
        graph=graph,
        sync_result=sync_result,
    )
    return outcome


async def _push_tree_to_wdk(
    *,
    nodes: list[StrategyStep],
    graph_record_type: str,
    site_id: str,
    sync_state: WDKSyncState,
    outcome: BuildOutcome,
) -> None:
    """Push every node in DFS order, recording per-step failures + skips.

    Each leaf/transform's parameters are validated against the *refreshed*
    WDK param spec (which honors dependent-param chains via
    ``refreshed-dependent-params``) before any HTTP push, so the agent
    never gets a chance to send WDK an invalid `go_term_slim` etc and
    burn a roundtrip on a deterministic 422.
    """
    failed_node_ids: set[str] = set()
    steps_by_id = {node.id: node for node in nodes}
    callbacks = make_validation_callbacks(site_id)
    for node in nodes:
        if _has_failed_descendant(node, failed_node_ids, steps_by_id):
            outcome.skipped_step_ids.append(node.id)
            continue
        search_name = wdk_search_name(node)
        push_parameters: dict[str, ParamValue] = dict(node.parameters)
        if search_name != COMBINE_SEARCH_NAME:
            try:
                push_parameters = await validate_parameters(
                    SearchContext(
                        site_id=site_id,
                        record_type=graph_record_type,
                        search_name=search_name,
                    ),
                    parameters=dict(node.parameters),
                    callbacks=callbacks,
                )
            except ValidationError as exc:
                detail = exc.detail or exc.title
                sync_state.wdk_push_errors[node.id] = detail
                failed_node_ids.add(node.id)
                outcome.failed_steps.append(
                    StepPushFailure(
                        step_id=node.id,
                        search_name=search_name,
                        error=detail,
                    ),
                )
                continue
        wdk_id, _validation, push_error = await push_step_to_wdk(
            sync_state=sync_state,
            step=node,
            site_id=site_id,
            record_type=graph_record_type,
            search_name=search_name,
            parameters=push_parameters,
        )
        if push_error:
            sync_state.wdk_push_errors[node.id] = push_error
            failed_node_ids.add(node.id)
            outcome.failed_steps.append(
                StepPushFailure(
                    step_id=node.id,
                    search_name=search_name,
                    error=push_error,
                ),
            )
            continue
        if wdk_id is not None:
            outcome.pushed_step_ids.append(node.id)


def _has_failed_descendant(
    node: StrategyStep,
    failed_ids: set[str],
    steps: dict[str, StrategyStep],
) -> bool:
    """True if any DFS-descendant of ``node`` already failed its push."""
    for input_id in node.inputs():
        if input_id in failed_ids:
            return True
        child = steps.get(input_id)
        if child is not None and _has_failed_descendant(child, failed_ids, steps):
            return True
    return False
