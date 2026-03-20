"""User data management - purge endpoints.

Thin HTTP adapter; all business logic lives in
``veupath_chatbot.services.user_data``.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.user_data import purge_user_data
from veupath_chatbot.transport.http.deps import CurrentUser, StreamRepo

router = APIRouter(prefix="/api/v1/user", tags=["user"])


@router.delete("/data")
async def purge_user_data_endpoint(
    user_id: CurrentUser,
    stream_repo: StreamRepo,
    site_id: str | None = Query(None, alias="siteId"),
    *,
    delete_wdk: Annotated[bool, Query(alias="deleteWdk")] = False,
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
    result = await purge_user_data(
        session=stream_repo.session,
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
