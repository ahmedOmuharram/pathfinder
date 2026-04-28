"""User-driven insert of a saved WDK strategy as a combine input.

This is the non-agent equivalent of the
``ai.tools.standalone.strategy.insert_saved_strategy`` tool. The agent
calls the tool inside an LLM turn; the HTTP endpoint calls this service
directly when the user clicks "Insert saved here…" in the strategy rail.
Both end up using the same building blocks (clone with fresh ids → push
to WDK → record consumer reference).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pathfinder.ai.graph.runtime import AgentDeps, DBSessionFactory
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.persistence.repositories.conversation import (
    ConversationRepository,
    ConversationUpdate,
)
from pathfinder.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
)
from pathfinder.platform.logging import get_logger
from pathfinder.services.strategies.save_substrategy import (
    deep_clone_with_fresh_ids,
)
from pathfinder.services.strategies.spec_build import (
    build_strategy_from_spec,
)
from pathfinder.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)

logger = get_logger(__name__)


@dataclass
class InsertSavedResult:
    wdk_strategy_id: int
    inserted_saved_wdk_strategy_id: int
    inserted_saved_name: str
    combine_step_id: str


def _build_new_root(
    *,
    graph: StrategyGraph,
    target_step_id: str,
    cloned_secondary: StrategyStepNode,
    operator: CombineOp,
    expanded_strategy_id: int,
    expanded_name: str,
) -> tuple[StrategyStepNode, str]:
    """Wrap ``target_step_id`` in a new combine that takes the saved subtree."""
    target_node = graph.steps[target_step_id]
    new_combine = StrategyStepNode(
        search_name="__combine__",
        operator=operator,
        primary_input=target_node,
        secondary_input=cloned_secondary,
        expanded_strategy_id=expanded_strategy_id,
        expanded_name=expanded_name,
    )
    parent_info = graph.find_parent(target_step_id)
    if parent_info is None:
        return new_combine, new_combine.id
    parent, slot = parent_info
    field = "primary_input" if slot == "primary" else "secondary_input"
    current = parent.model_copy(update={field: new_combine})
    while True:
        up = graph.find_parent(current.id)
        if up is None:
            return current, new_combine.id
        up_parent, up_slot = up
        up_field = "primary_input" if up_slot == "primary" else "secondary_input"
        current = up_parent.model_copy(update={up_field: current})


async def insert_saved_into_conversation(  # noqa: PLR0913
    *,
    session: StrategySession,
    site_id: str,
    conversation_id: UUID,
    db_session_factory: DBSessionFactory,
    target_step_id: str,
    saved_wdk_strategy_id: int,
    operator: CombineOp,
) -> InsertSavedResult:
    """Materialize an inserted saved strategy and push to WDK.

    This drives the same path as the agent tool: load the saved WDK
    strategy, deep-clone its tree with fresh local ids, wrap the target
    step in a new combine carrying ``expanded_*`` fields, then build via
    ``build_strategy_from_spec`` so per-step pushes are retryable.
    """
    graph = session.get_graph(None)
    if graph is None:
        raise ValidationError(
            title="no active strategy",
            detail="cannot insert into a conversation with no active graph",
        )
    if target_step_id not in graph.steps:
        raise NotFoundError(
            code=ErrorCode.STEP_NOT_FOUND,
            title="step not found",
            detail=(
                f"step {target_step_id!r} not in active graph "
                f"(available: {sorted(graph.steps)[:20]})"
            ),
        )

    api = get_strategy_api(site_id)
    try:
        saved = await api.get_strategy(saved_wdk_strategy_id)
    except AppError as exc:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="saved strategy not found",
            detail=(
                f"could not load saved WDK strategy "
                f"{saved_wdk_strategy_id}: {exc}"
            ),
        ) from exc

    saved_ast = build_snapshot_from_wdk(saved)
    cloned_secondary = deep_clone_with_fresh_ids(saved_ast.root)
    new_full_root, combine_step_id = _build_new_root(
        graph=graph,
        target_step_id=target_step_id,
        cloned_secondary=cloned_secondary,
        operator=operator,
        expanded_strategy_id=saved_wdk_strategy_id,
        expanded_name=saved.name or f"Saved strategy {saved_wdk_strategy_id}",
    )

    saved_label = saved.name or f"Saved strategy {saved_wdk_strategy_id}"
    deps = AgentDeps(
        site_id=site_id,
        strategy_session=session,
        conversation_id=conversation_id,
        db_session_factory=db_session_factory,
    )
    outcome = await build_strategy_from_spec(
        deps=deps,
        root=new_full_root,
        name=graph.name,
        description=graph.description,
    )
    if outcome.failed_steps:
        first = outcome.failed_steps[0]
        raise ValidationError(
            title="insert pushed partial state",
            detail=(
                f"failed to push step {first.step_id!r} "
                f"({first.search_name}): {first.error}"
            ),
        )

    await _record_consumer(
        db_session_factory=db_session_factory,
        conversation_id=conversation_id,
        wdk_strategy_id=saved_wdk_strategy_id,
    )

    return InsertSavedResult(
        wdk_strategy_id=outcome.wdk_strategy_id or 0,
        inserted_saved_wdk_strategy_id=saved_wdk_strategy_id,
        inserted_saved_name=saved_label,
        combine_step_id=combine_step_id,
    )


async def _record_consumer(
    *,
    db_session_factory: DBSessionFactory,
    conversation_id: UUID,
    wdk_strategy_id: int,
) -> None:
    async with db_session_factory() as db:
        repo = ConversationRepository(db)
        conv = await repo.get_by_id(conversation_id)
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
        await db.commit()
