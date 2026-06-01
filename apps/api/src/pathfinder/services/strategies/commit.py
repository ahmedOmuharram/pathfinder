from dataclasses import dataclass, field

from pathfinder.domain.strategy.operations import GraphOperation
from pathfinder.domain.strategy.operations.apply import apply_operation
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.platform.errors import (
    AppError,
    PartialPushError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.strategies.context import StrategyMutationContext
from pathfinder.services.strategies.persist import (
    persist_strategy_ast_to_conversation,
)
from pathfinder.services.strategies.reconcile import (
    reconcile_sync_state_with_wdk,
)
from pathfinder.services.strategies.step_push_planner import (
    plan_step_pushes,
    topology_changed,
)
from pathfinder.services.strategies.step_wdk_push import push_steps_with_plan
from pathfinder.services.strategies.sync import SyncResult, sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state
from pathfinder.services.strategies.wdk_step_cleanup import (
    delete_orphaned_wdk_steps,
)

logger = get_logger(__name__)


@dataclass
class CommitResult:
    description: str
    dropped_step_ids: list[str] = field(default_factory=list)
    sync_result: SyncResult | None = None


def _require_graph(deps: StrategyMutationContext) -> StrategyGraph:
    graph = deps.strategy_session.get_graph(None)
    if graph is None:
        raise ValidationError(
            title="No active strategy graph",
            detail="apply_and_commit requires an initialized graph in the session",
        )
    return graph


async def apply_and_commit(
    *,
    deps: StrategyMutationContext,
    op: GraphOperation,
) -> CommitResult:
    graph = _require_graph(deps)
    sync_state = ensure_sync_state(deps.strategy_session)
    snapshot = graph.to_strategy_ast(sync_state=sync_state)
    # Deep-copy: apply_operation mutates the live nodes in-place, so a shallow
    # snapshot would alias the post-mutation state and defeat plan_step_pushes
    # change detection.
    old_ast = snapshot.model_copy(deep=True) if snapshot is not None else None

    result = apply_operation(graph, op)
    if graph.steps:
        graph.save_history(result.description)

    new_ast = graph.to_strategy_ast(sync_state=sync_state)

    sync_result = await _commit_to_wdk(
        deps=deps,
        graph=graph,
        old_ast=old_ast,
        new_ast=new_ast,
        dropped_step_ids=result.dropped_step_ids,
    )

    await persist_strategy_ast_to_conversation(
        deps=deps,
        graph=graph,
        sync_result=sync_result.sync_result,
    )

    if sync_result.failed_step_ids:
        raise PartialPushError(
            succeeded_step_ids=sync_result.succeeded_step_ids,
            failed_step_ids=sync_result.failed_step_ids,
        )

    return CommitResult(
        description=result.description,
        dropped_step_ids=result.dropped_step_ids,
        sync_result=sync_result.sync_result,
    )


@dataclass
class _WDKCommitOutcome:
    succeeded_step_ids: list[str]
    failed_step_ids: list[str]
    sync_result: SyncResult | None


async def _commit_to_wdk(
    *,
    deps: StrategyMutationContext,
    graph: StrategyGraph,
    old_ast: StrategyAst | None,
    new_ast: StrategyAst | None,
    dropped_step_ids: list[str],
) -> _WDKCommitOutcome:
    sync_state = ensure_sync_state(deps.strategy_session)
    api = get_strategy_api(deps.site_id)

    await reconcile_sync_state_with_wdk(
        sync_state,
        deps.site_id,
        sync_state.wdk_strategy_id,
    )

    succeeded: list[str] = []
    failed: list[str] = []
    if new_ast is not None:
        plan = plan_step_pushes(
            old_ast=old_ast,
            new_ast=new_ast,
            existing_wdk_ids=sync_state.wdk_step_ids,
        )
        push_outcome = await push_steps_with_plan(graph, sync_state, deps.site_id, plan)
        succeeded = push_outcome.succeeded
        failed = push_outcome.failed

    wdk_ids_to_delete: list[int] = []
    for sid in dropped_step_ids:
        wdk_id = sync_state.wdk_step_ids.pop(sid, None)
        sync_state.step_counts.pop(sid, None)
        sync_state.step_validations.pop(sid, None)
        sync_state.wdk_push_errors.pop(sid, None)
        if wdk_id is not None:
            wdk_ids_to_delete.append(wdk_id)
    if wdk_ids_to_delete:
        leftover = await delete_orphaned_wdk_steps(api, wdk_ids_to_delete)
        if leftover:
            logger.warning(
                "Some orphaned WDK steps could not be deleted",
                step_ids=leftover,
            )

    sync_result: SyncResult | None = None
    if (
        not failed
        and new_ast is not None
        and graph.steps
        and topology_changed(old_ast, new_ast)
    ):
        try:
            sync_result = await sync_strategy_for_site(
                graph=graph,
                sync_state=sync_state,
                site_id=deps.site_id,
                strategy_name=graph.name,
            )
        except AppError as exc:
            logger.warning(
                "sync_strategy_for_site failed; persisting partial state",
                error=str(exc),
            )

    return _WDKCommitOutcome(
        succeeded_step_ids=succeeded,
        failed_step_ids=failed,
        sync_result=sync_result,
    )
