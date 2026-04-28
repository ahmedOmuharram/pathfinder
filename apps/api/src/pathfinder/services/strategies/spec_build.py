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

from dataclasses import dataclass, field

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
    walk_step_tree,
)
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.services.strategies.persist import (
    persist_strategy_ast_to_conversation,
)
from pathfinder.services.strategies.reconcile import reconcile_sync_state_with_wdk
from pathfinder.services.strategies.step_wdk_push import push_step_to_wdk
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import WDKSyncState, ensure_sync_state

logger = get_logger(__name__)


@dataclass
class StepPushFailure:
    step_id: str
    search_name: str
    error: str


@dataclass
class BuildOutcome:
    """Structured result of a declarative strategy build."""

    pushed_step_ids: list[str] = field(default_factory=list)
    failed_steps: list[StepPushFailure] = field(default_factory=list)
    skipped_step_ids: list[str] = field(default_factory=list)
    wdk_strategy_id: int | None = None
    wdk_url: str | None = None
    counts: dict[str, int | None] = field(default_factory=dict)
    root_count: int | None = None
    zero_step_ids: list[str] = field(default_factory=list)

    @property
    def fully_succeeded(self) -> bool:
        return not self.failed_steps and not self.skipped_step_ids


async def build_strategy_from_spec(
    *,
    deps: AgentDeps,
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

    nodes = walk_step_tree(root)

    graph.steps.clear()
    graph.roots.clear()
    for node in nodes:
        graph.add_step(node)
    if name is not None:
        graph.name = name
    if description is not None:
        graph.description = description

    sync_state = ensure_sync_state(session)
    await reconcile_sync_state_with_wdk(
        sync_state, deps.site_id, sync_state.wdk_strategy_id,
    )

    # Persist the local AST immediately so the rail reflects the agent's
    # declared structure even if WDK pushes fail or take time.
    await persist_strategy_ast_to_conversation(
        deps=deps, graph=graph, sync_result=None,
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
            deps=deps, graph=graph, sync_result=None,
        )
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
            deps=deps, graph=graph, sync_result=None,
        )
        outcome.failed_steps.append(
            StepPushFailure(
                step_id=root.id,
                search_name=root.search_name,
                error=str(exc),
            ),
        )
        return outcome

    outcome.wdk_strategy_id = sync_result.wdk_strategy_id
    outcome.wdk_url = sync_result.wdk_url
    outcome.counts = {str(k): v for k, v in sync_result.counts.items()}
    outcome.root_count = sync_result.root_count
    outcome.zero_step_ids = list(sync_result.zero_step_ids)

    await persist_strategy_ast_to_conversation(
        deps=deps, graph=graph, sync_result=sync_result,
    )
    return outcome


async def _push_tree_to_wdk(
    *,
    nodes: list[StrategyStepNode],
    graph_record_type: str,
    site_id: str,
    sync_state: WDKSyncState,
    outcome: BuildOutcome,
) -> None:
    """Push every node in DFS order, recording per-step failures + skips."""
    failed_node_ids: set[str] = set()
    for node in nodes:
        if _has_failed_descendant(node, failed_node_ids):
            outcome.skipped_step_ids.append(node.id)
            continue
        search_name = node.search_name or COMBINE_SEARCH_NAME
        wdk_id, _validation, push_error = await push_step_to_wdk(
            sync_state=sync_state,
            step=node,
            site_id=site_id,
            record_type=graph_record_type,
            search_name=search_name,
            parameters=node.parameters or {},
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
    node: StrategyStepNode, failed_ids: set[str],
) -> bool:
    """True if any DFS-descendant of ``node`` already failed its push."""
    if node.primary_input is not None:
        if node.primary_input.id in failed_ids:
            return True
        if _has_failed_descendant(node.primary_input, failed_ids):
            return True
    if node.secondary_input is not None:
        if node.secondary_input.id in failed_ids:
            return True
        if _has_failed_descendant(node.secondary_input, failed_ids):
            return True
    return False
