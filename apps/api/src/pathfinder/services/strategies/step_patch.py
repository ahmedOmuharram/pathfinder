from typing import Protocol
from uuid import UUID

from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import ConversationUpdate
from pathfinder.platform.errors import ErrorCode, NotFoundError, PartialPushError
from pathfinder.platform.logging import get_logger
from pathfinder.services.strategies.plan_normalize import (
    canonicalize_strategy_ast_parameters,
)
from pathfinder.services.strategies.plan_validation import validate_plan_or_raise
from pathfinder.services.strategies.reconcile import reconcile_sync_state_with_wdk
from pathfinder.services.strategies.schemas import (
    StepResponse,
    step_response_from_strategy_ast,
)
from pathfinder.services.strategies.session_factory import build_strategy_session
from pathfinder.services.strategies.step_push_planner import (
    CreateAction,
    RecreateAction,
    plan_step_pushes,
    topology_changed,
)
from pathfinder.services.strategies.step_wdk_push import push_steps_with_plan
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state
from pathfinder.transport.http.schemas import StepPatchRequest

logger = get_logger(__name__)


class StepPatchRepo(Protocol):
    async def get_by_id_with_strategy_lock(
        self, conversation_id: UUID
    ) -> Conversation | None: ...
    async def update_conversation(
        self, conversation_id: UUID, upd: ConversationUpdate
    ) -> None: ...
    async def commit_partial(self) -> None:
        """Commit pending writes early so subsequent failures don't roll them back.

        The HTTP request session middleware commits at end-of-request, but a
        raised `PartialPushError` short-circuits that and triggers a rollback.
        Calling `commit_partial()` before raising preserves the partial WDK
        push state — without this, a retry would re-CREATE already-pushed
        steps and produce duplicates in WDK.
        """
        ...


def _find_step(root: StrategyStepNode, step_id: str) -> StrategyStepNode | None:
    for node in walk_step_tree(root):
        if node.id == step_id:
            return node
    return None


def _apply_patch_to_node(target: StrategyStepNode, patch: StepPatchRequest) -> None:
    fields = patch.model_fields_set
    if "parameters" in fields and patch.parameters is not None:
        target.parameters = patch.parameters
    if "operator" in fields:
        target.operator = patch.operator
    if "display_name" in fields:
        target.display_name = patch.display_name
    if "colocation_params" in fields:
        target.colocation_params = patch.colocation_params
    if "wdk_weight" in fields:
        target.wdk_weight = patch.wdk_weight
    if "search_name" in fields and patch.search_name is not None:
        target.search_name = patch.search_name


async def apply_step_patch(
    *,
    conv_repo: StepPatchRepo,
    strategy_id: UUID,
    step_id: str,
    site_id: str,
    patch: StepPatchRequest,
) -> StepResponse:
    conversation = await conv_repo.get_by_id_with_strategy_lock(strategy_id)
    if conversation is None or conversation.strategy_ast is None:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )

    old_ast = StrategyAst.model_validate(conversation.strategy_ast)
    new_ast = old_ast.model_copy(deep=True)
    target = _find_step(new_ast.root, step_id)
    if target is None:
        raise NotFoundError(
            code=ErrorCode.STEP_NOT_FOUND,
            title="Step not found",
            detail=f"Step '{step_id}' not in strategy '{strategy_id}'",
        )

    logger.info(
        "DEBUG step_patch.received",
        strategy_id=str(strategy_id),
        step_id=step_id,
        fields=sorted(patch.model_fields_set),
    )

    _apply_patch_to_node(target, patch)
    new_ast = validate_plan_or_raise(new_ast.model_dump(exclude_none=True))
    new_ast = await canonicalize_strategy_ast_parameters(
        strategy_ast=new_ast, site_id=site_id
    )

    persisted = PersistedStrategyGraph(
        id=str(strategy_id),
        name=conversation.name,
        strategy_ast=new_ast,
        wdk_strategy_id=conversation.wdk_strategy_id,
    )
    session = build_strategy_session(site_id=site_id, strategy_graph=persisted)
    graph = session.get_graph(None)
    sync_skipped = True
    new_wdk_strategy_id: int | None = conversation.wdk_strategy_id
    push_outcome_failed: list[str] = []
    push_outcome_succeeded: list[str] = []
    if graph is not None:
        sync_state = ensure_sync_state(session)
        sync_state.last_pushed_ast = old_ast

        await reconcile_sync_state_with_wdk(
            sync_state, site_id, conversation.wdk_strategy_id,
        )

        plan = plan_step_pushes(
            old_ast=sync_state.last_pushed_ast,
            new_ast=new_ast,
            existing_wdk_ids=sync_state.wdk_step_ids,
        )
        has_recreate = any(
            isinstance(p.action, RecreateAction) for p in plan
        )
        has_create = any(isinstance(p.action, CreateAction) for p in plan)
        sync_skipped = not (
            topology_changed(old_ast, new_ast) or has_recreate or has_create
        )
        logger.info(
            "DEBUG step_patch.plan",
            strategy_id=str(strategy_id),
            step_id=step_id,
            plan=[(p.step_id, p.action.kind) for p in plan],
            sync_skipped=sync_skipped,
        )

        push_outcome = await push_steps_with_plan(graph, sync_state, site_id, plan)
        push_outcome_failed = push_outcome.failed
        push_outcome_succeeded = push_outcome.succeeded

        if not push_outcome.partial and not sync_skipped:
            sync_result = await sync_strategy_for_site(
                graph=graph,
                sync_state=sync_state,
                site_id=site_id,
                strategy_name=conversation.name,
            )
            new_wdk_strategy_id = sync_result.wdk_strategy_id

        new_ast = new_ast.model_copy(
            update={
                "wdk_step_ids": dict(sync_state.wdk_step_ids),
                "step_counts": dict(sync_state.step_counts),
                "step_validations": dict(sync_state.step_validations),
            }
        )
        sync_state.last_pushed_ast = new_ast

    await conv_repo.update_conversation(
        strategy_id,
        ConversationUpdate(
            strategy_ast=new_ast,
            record_type=new_ast.record_type,
            step_count=len(walk_step_tree(new_ast.root)),
            wdk_strategy_id=new_wdk_strategy_id,
            wdk_strategy_id_set=True,
        ),
    )

    if push_outcome_failed:
        # Persist partial WDK push state before raising — see PartialPushError.
        await conv_repo.commit_partial()
        raise PartialPushError(
            succeeded_step_ids=push_outcome_succeeded,
            failed_step_ids=push_outcome_failed,
        )

    refreshed_target = _find_step(new_ast.root, step_id)
    if refreshed_target is None:
        raise NotFoundError(
            code=ErrorCode.STEP_NOT_FOUND,
            title="Step not found after patch",
            detail=f"Step '{step_id}' missing from updated AST",
        )
    response = step_response_from_strategy_ast(new_ast, refreshed_target)
    logger.info(
        "DEBUG step_patch.response",
        strategy_id=str(strategy_id),
        step_id=step_id,
        operator=response.operator,
        search_name=response.search_name,
    )
    return response
