"""Importing a WDK strategy lands in the side table and reads back from it."""

from __future__ import annotations

from uuid import UUID

from assistant_core.platform.db import async_session_factory

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.saved_strategy import (
    SavedStrategyRepository,
)
from pathfinder.services.strategies.wdk_sync import (
    WdkChatSpec,
    plan_needs_detail_fetch,
    upsert_chat,
    upsert_summary_chat,
)

WDK_ID = 881001


def _spec(name: str, *, step_count: int = 1) -> WdkChatSpec:
    return WdkChatSpec(
        wdk_id=WDK_ID,
        name=name,
        strategy_ast=StrategyAst(
            record_type="transcript",
            root=StrategyStepNode(id="step_a", search_name="GenesByTaxon"),
        ),
        record_type="transcript",
        is_saved=True,
        step_count=step_count,
    )


async def test_importing_a_wdk_strategy_creates_the_side_row(
    authed_user_id: UUID,
) -> None:
    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        conversation = await upsert_chat(
            conv_repo=repo,
            user_id=authed_user_id,
            site_id="plasmodb",
            spec=_spec("imported"),
        )
        await session.commit()
        conversation_id = conversation.id

    async with async_session_factory() as session:
        found = await SavedStrategyRepository(session).get_by_wdk_strategy_id(
            authed_user_id,
            WDK_ID,
        )

    assert found is not None
    conversation, strategy = found
    assert conversation.id == conversation_id
    assert strategy.wdk_strategy_id == WDK_ID
    assert strategy.record_type == "transcript"
    assert strategy.is_saved is True
    assert strategy.step_count == 1
    assert plan_needs_detail_fetch(strategy) is False


async def test_a_second_import_updates_the_same_thread(authed_user_id: UUID) -> None:
    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        first = await upsert_chat(
            conv_repo=repo,
            user_id=authed_user_id,
            site_id="plasmodb",
            spec=_spec("imported"),
        )
        await session.commit()
        first_id = first.id

    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        second = await upsert_chat(
            conv_repo=repo,
            user_id=authed_user_id,
            site_id="plasmodb",
            spec=_spec("renamed upstream", step_count=6),
        )
        await session.commit()

        assert second.id == first_id
        assert second.name == "renamed upstream"
        second_strategy = await repo.get_strategy(second.id)
        assert second_strategy.wdk_strategy_id == WDK_ID
        assert second_strategy.step_count == 6


async def test_a_summary_import_leaves_the_plan_unfetched(
    authed_user_id: UUID,
) -> None:
    summary = WDKStrategySummary(
        strategy_id=WDK_ID,
        name="summary only",
        root_step_id=1,
        record_class_name="transcript",
        is_saved=False,
        estimated_size=137,
        leaf_and_transform_step_count=3,
    )

    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        conversation = await upsert_summary_chat(
            summary,
            conv_repo=repo,
            user_id=authed_user_id,
            site_id="plasmodb",
        )
        await session.commit()

    assert conversation is not None
    async with async_session_factory() as session:
        strategy = await ConversationRepository(session).get_strategy(conversation.id)
    assert strategy.wdk_strategy_id == WDK_ID
    assert strategy.estimated_size == 137
    assert strategy.step_count == 3
    assert strategy.strategy_ast == {}
    assert plan_needs_detail_fetch(strategy) is True


async def test_pruning_drops_a_thread_whose_wdk_strategy_is_gone(
    authed_user_id: UUID,
) -> None:
    async with async_session_factory() as session:
        repo = ConversationRepository(session)
        await upsert_chat(
            conv_repo=repo,
            user_id=authed_user_id,
            site_id="plasmodb",
            spec=_spec("imported"),
        )
        await session.commit()

    async with async_session_factory() as session:
        saved = SavedStrategyRepository(session)
        pruned = await saved.prune_wdk_orphans(authed_user_id, "plasmodb", set())
        await session.commit()

        assert pruned == 1
        assert await saved.get_by_wdk_strategy_id(authed_user_id, WDK_ID) is None
