"""User data purge service.

Business logic for purging user data across all local stores (PostgreSQL,
in-memory caches) and optionally deleting WDK strategies.

The transport layer (``transport.http.routers.user_data``) is a thin HTTP
adapter that delegates to this module.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.integrations.veupathdb.factory import (
    get_strategy_api,
    list_sites,
)
from pathfinder.persistence.models import (
    ControlSet,
    Conversation,
    ExperimentRow,
    GeneSetRow,
)
from pathfinder.platform.errors import WDKError
from pathfinder.platform.logging import get_logger
from pathfinder.services.gene_sets.store import get_gene_set_store

logger = get_logger(__name__)


@dataclass(frozen=True)
class PurgeResult:
    """Summary of a user data purge operation."""

    hard_deleted: int
    dismissed: int
    wdk_strategies: int
    gene_sets: int
    experiments: int
    control_sets: int


async def purge_user_data(
    *,
    session: AsyncSession,
    user_id: UUID,
    site_id: str | None,
    delete_wdk: bool,
) -> PurgeResult:
    """Purge user data from all local stores.

    When ``delete_wdk=False``: non-WDK chats are hard-deleted, WDK-linked chats
    are **dismissed** so WDK sync won't re-import them.

    When ``delete_wdk=True``: everything is hard-deleted locally AND all WDK
    strategies are deleted from VEuPathDB.

    Always deletes: gene sets, experiments, control sets.
    """
    # 1. Find all conversations (for WDK cleanup)
    conversation_query = select(Conversation).where(Conversation.user_id == user_id)
    if site_id:
        conversation_query = conversation_query.where(Conversation.site_id == site_id)
    conversations = list((await session.execute(conversation_query)).scalars().all())
    conversation_ids = [str(c.id) for c in conversations]

    # 2. Delete WDK strategies (only when explicitly requested)
    wdk_deleted = await _purge_wdk_strategies(site_id, delete_wdk=delete_wdk)

    # 3. Handle conversations
    dismissed_count = 0
    hard_deleted_count = 0

    if delete_wdk:
        conv_del = delete(Conversation).where(Conversation.user_id == user_id)
        if site_id:
            conv_del = conv_del.where(Conversation.site_id == site_id)
        sr = cast("CursorResult[object]", await session.execute(conv_del))
        hard_deleted_count = sr.rowcount or 0
    elif conversation_ids:
        all_uuids = [UUID(conv_id) for conv_id in conversation_ids]
        await session.execute(
            update(Conversation)
            .where(Conversation.id.in_(all_uuids))
            .values(dismissed_at=datetime.now(UTC))
        )
        dismissed_count = len(conversation_ids)

    # 4. Delete gene sets, experiments, control sets
    pg_gene_sets, pg_experiments, pg_control_sets = await _purge_related_data(
        session, user_id, site_id
    )

    await session.commit()

    # 5. Clear in-memory caches so stale data doesn't reappear
    _clear_gene_set_cache(user_id, site_id)

    strategies_handled = hard_deleted_count + dismissed_count
    logger.info(
        "Purged user data",
        user_id=str(user_id),
        site_id=site_id,
        delete_wdk=delete_wdk,
        strategies=strategies_handled,
        wdk_strategies=wdk_deleted,
        gene_sets=pg_gene_sets,
        experiments=pg_experiments,
        control_sets=pg_control_sets,
    )

    return PurgeResult(
        hard_deleted=hard_deleted_count,
        dismissed=dismissed_count,
        wdk_strategies=wdk_deleted,
        gene_sets=pg_gene_sets,
        experiments=pg_experiments,
        control_sets=pg_control_sets,
    )


async def _purge_wdk_strategies(site_id: str | None, *, delete_wdk: bool) -> int:
    """Delete WDK strategies when explicitly requested."""
    if not delete_wdk:
        return 0

    sites_to_purge: set[str] = set()
    if site_id:
        sites_to_purge.add(site_id)
    else:
        sites_to_purge.update(s.id for s in list_sites())

    # Delete concurrently (bounded) — a sequential per-strategy loop across all
    # sites can run for minutes and trip the upstream connection's idle reset.
    semaphore = asyncio.Semaphore(10)
    wdk_deleted = 0
    for purge_site in sites_to_purge:
        try:
            api = get_strategy_api(purge_site)
            wdk_strategies = await api.list_strategies()
        except (ValueError, RuntimeError, WDKError) as exc:
            logger.debug("WDK purge skipped for site", site=purge_site, error=str(exc))
            continue

        async def _delete_one(strategy_id: int, *, site: str = purge_site) -> int:
            async with semaphore:
                try:
                    await get_strategy_api(site).delete_strategy(strategy_id)
                except (ValueError, RuntimeError, WDKError) as exc:
                    logger.warning(
                        "Failed to delete WDK strategy during user data purge",
                        wdk_strategy_id=strategy_id,
                        site=site,
                        error=str(exc),
                    )
                    return 0
                return 1

        outcomes = await asyncio.gather(
            *(_delete_one(s.strategy_id) for s in wdk_strategies)
        )
        wdk_deleted += sum(outcomes)
    return wdk_deleted


async def _purge_related_data(
    session: AsyncSession,
    user_id: UUID,
    site_id: str | None,
) -> tuple[int, int, int]:
    """Delete gene sets, experiments, and control sets."""
    gs_del = delete(GeneSetRow).where(GeneSetRow.user_id == user_id)
    if site_id:
        gs_del = gs_del.where(GeneSetRow.site_id == site_id)
    gr = cast("CursorResult[object]", await session.execute(gs_del))
    pg_gene_sets = gr.rowcount or 0

    exp_del = delete(ExperimentRow).where(ExperimentRow.user_id == user_id)
    if site_id:
        exp_del = exp_del.where(ExperimentRow.site_id == site_id)
    er = cast("CursorResult[object]", await session.execute(exp_del))
    pg_experiments = er.rowcount or 0

    cs_del = delete(ControlSet).where(ControlSet.user_id == user_id)
    if site_id:
        cs_del = cs_del.where(ControlSet.site_id == site_id)
    cr = cast("CursorResult[object]", await session.execute(cs_del))
    pg_control_sets = cr.rowcount or 0

    return pg_gene_sets, pg_experiments, pg_control_sets


def _clear_gene_set_cache(user_id: UUID, site_id: str | None) -> None:
    """Clear in-memory gene set cache entries."""
    try:
        cache = get_gene_set_store()
        to_evict = [
            gid
            for gid, gs in cache._cache.items()
            if gs.user_id == user_id and (site_id is None or gs.site_id == site_id)
        ]
        for gid in to_evict:
            cache._cache.pop(gid, None)
    except (RuntimeError, KeyError) as exc:
        logger.warning(
            "Failed to clear gene set cache during user data purge",
            user_id=str(user_id),
            error=str(exc),
        )
