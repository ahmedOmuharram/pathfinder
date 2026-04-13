"""User data management - purge endpoints.

Thin HTTP adapter; all business logic lives in
``pathfinder.services.user_data``.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from pathfinder.platform.redis import get_redis
from pathfinder.platform.types import JSONObject
from pathfinder.services.user_data import purge_user_data
from pathfinder.transport.http.deps import ChatRepo, CurrentUser

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.delete("/data")
async def purge_user_data_endpoint(
    user_id: CurrentUser,
    chat_repo: ChatRepo,
    site_id: str | None = Query(None, alias="siteId"),
    *,
    delete_wdk: Annotated[bool, Query(alias="deleteWdk")] = False,
) -> JSONObject:
    """Purge user data from all local stores.

    When ``deleteWdk=false`` (default): non-WDK chats are hard-deleted,
    WDK-linked chats are **dismissed** so WDK sync won't re-import them.
    The strategies remain on VEuPathDB but PathFinder ignores them.

    When ``deleteWdk=true``: everything is hard-deleted locally AND all
    WDK strategies are deleted from VEuPathDB.

    Always deletes: gene sets, experiments, control sets, Redis streams.

    Pass ``?siteId=X`` to limit to one site, or omit for everything.
    """
    result = await purge_user_data(
        session=chat_repo.session,
        redis=get_redis(),
        user_id=user_id,
        site_id=site_id,
        delete_wdk=delete_wdk,
    )

    strategies_handled = result.hard_deleted + result.dismissed
    return {
        "ok": True,
        "deleted": {
            "strategies": strategies_handled,
            "wdkStrategies": result.wdk_strategies,
            "redisStreams": result.redis_streams,
            "geneSets": result.gene_sets,
            "experiments": result.experiments,
            "controlSets": result.control_sets,
        },
    }
