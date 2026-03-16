"""User data management — purge endpoints."""

import contextlib
from typing import cast

from fastapi import APIRouter, Query
from sqlalchemy import CursorResult, delete, select

from veupath_chatbot.persistence.models import (
    ControlSet,
    ExperimentRow,
    GeneSetRow,
    Stream,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.deps import CurrentUser, StreamRepo

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.delete("/data")
async def purge_user_data(
    user_id: CurrentUser,
    stream_repo: StreamRepo,
    site_id: str | None = Query(None, alias="siteId"),
    delete_wdk: bool = Query(False, alias="deleteWdk"),
) -> JSONObject:
    """Purge user data from all local stores.

    When ``deleteWdk=false`` (default): non-WDK streams are hard-deleted,
    WDK-linked projections are **dismissed** so WDK sync won't re-import
    them. The strategies remain on VEuPathDB but PathFinder ignores them.

    When ``deleteWdk=true``: everything is hard-deleted locally AND all
    WDK strategies are deleted from VEuPathDB.

    Always deletes: gene sets, experiments, control sets, Redis streams.

    Pass ``?siteId=X`` to limit to one site, or omit for everything.
    """
    session = stream_repo.session
    redis = get_redis()
    uid_str = str(user_id)

    # ── 1. Find all streams (for Redis + WDK cleanup) ──────────────
    stream_query = select(Stream).where(Stream.user_id == user_id)
    if site_id:
        stream_query = stream_query.where(Stream.site_id == site_id)
    streams = list((await session.execute(stream_query)).scalars().all())
    stream_ids = [str(s.id) for s in streams]

    # ── 2. Delete WDK strategies (only when explicitly requested) ──
    wdk_deleted = 0
    if delete_wdk:
        from veupath_chatbot.integrations.veupathdb.factory import (
            get_strategy_api,
            list_sites,
        )

        sites_to_purge: set[str] = set()
        if site_id:
            sites_to_purge.add(site_id)
        else:
            sites_to_purge.update(s.id for s in list_sites())

        for purge_site in sites_to_purge:
            try:
                api = get_strategy_api(purge_site)
                wdk_strategies = await api.list_strategies()
                for wdk_strat in wdk_strategies:
                    if not isinstance(wdk_strat, dict):
                        continue
                    wdk_id = wdk_strat.get("strategyId")
                    if wdk_id is not None:
                        try:
                            await api.delete_strategy(int(str(wdk_id)))
                            wdk_deleted += 1
                        except Exception as exc:
                            logger.warning(
                                "Failed to delete WDK strategy during user data purge",
                                wdk_strategy_id=wdk_id,
                                site=purge_site,
                                error=str(exc),
                            )
            except Exception as exc:
                logger.debug(
                    "WDK purge skipped for site", site=purge_site, error=str(exc)
                )

    # ── 4. Delete Redis streams ────────────────────────────────────
    redis_deleted = 0
    for sid in stream_ids:
        with contextlib.suppress(Exception):
            redis_deleted += int(await redis.delete(f"stream:{sid}"))

    # ── 5. Handle streams ──────────────────────────────────────────
    dismissed_count = 0
    hard_deleted_count = 0

    if delete_wdk:
        # Nuclear option: hard-delete ALL streams (cascade to projections).
        stream_del = delete(Stream).where(Stream.user_id == user_id)
        if site_id:
            stream_del = stream_del.where(Stream.site_id == site_id)
        sr = cast(CursorResult[object], await session.execute(stream_del))
        hard_deleted_count = sr.rowcount or 0
    else:
        from datetime import UTC, datetime

        from sqlalchemy import update

        from veupath_chatbot.persistence.models import StreamProjection

        # Dismiss ALL projections — prevents WDK sync from re-importing them.
        # We dismiss all (not just WDK-linked) to avoid a race condition where
        # auto-build assigns a wdk_strategy_id between classification and delete.
        if stream_ids:
            from uuid import UUID

            all_uuids = [UUID(sid) for sid in stream_ids]
            await session.execute(
                update(StreamProjection)
                .where(StreamProjection.stream_id.in_(all_uuids))
                .values(dismissed_at=datetime.now(UTC))
            )
            dismissed_count = len(stream_ids)

    # ── 6. Delete gene sets, experiments, control sets ─────────────
    gs_del = delete(GeneSetRow).where(GeneSetRow.user_id == uid_str)
    if site_id:
        gs_del = gs_del.where(GeneSetRow.site_id == site_id)
    gr = cast(CursorResult[object], await session.execute(gs_del))
    pg_gene_sets = gr.rowcount or 0

    exp_del = delete(ExperimentRow).where(ExperimentRow.user_id == uid_str)
    if site_id:
        exp_del = exp_del.where(ExperimentRow.site_id == site_id)
    er = cast(CursorResult[object], await session.execute(exp_del))
    pg_experiments = er.rowcount or 0

    cs_del = delete(ControlSet).where(ControlSet.user_id == user_id)
    if site_id:
        cs_del = cs_del.where(ControlSet.site_id == site_id)
    cr = cast(CursorResult[object], await session.execute(cs_del))
    pg_control_sets = cr.rowcount or 0

    await session.commit()

    # ── 7. Clear in-memory caches so stale data doesn't reappear ──
    try:
        from veupath_chatbot.services.gene_sets.store import get_gene_set_store

        cache = get_gene_set_store()
        for gs in list(cache.list_for_user(user_id, site_id=site_id)):
            cache._cache.pop(gs.id, None)
    except Exception as exc:
        logger.warning(
            "Failed to clear gene set cache during user data purge",
            user_id=uid_str,
            error=str(exc),
        )

    strategies_handled = hard_deleted_count + dismissed_count
    logger.info(
        "Purged user data",
        user_id=uid_str,
        site_id=site_id,
        delete_wdk=delete_wdk,
        strategies=strategies_handled,
        wdk_strategies=wdk_deleted,
        redis_streams=redis_deleted,
        gene_sets=pg_gene_sets,
        experiments=pg_experiments,
        control_sets=pg_control_sets,
    )

    return {
        "ok": True,
        "deleted": {
            "strategies": strategies_handled,
            "wdkStrategies": wdk_deleted,
            "redisStreams": redis_deleted,
            "geneSets": pg_gene_sets,
            "experiments": pg_experiments,
            "controlSets": pg_control_sets,
        },
    }
