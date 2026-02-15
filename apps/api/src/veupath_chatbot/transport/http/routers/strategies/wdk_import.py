"""WDK-backed strategy endpoints (open/import/sync/list)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast
from uuid import UUID

if TYPE_CHECKING:
    from veupath_chatbot.persistence.models import Strategy

from fastapi import APIRouter, Query, Response

from veupath_chatbot.integrations.veupathdb.factory import (
    get_site,
    get_strategy_api,
    list_sites,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import (
    StrategyAPI,
    is_internal_wdk_strategy_name,
    strip_internal_wdk_strategy_name,
)
from veupath_chatbot.platform.errors import (
    AppError,
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.strategies.serialization import count_steps_in_plan
from veupath_chatbot.services.strategies.wdk_snapshot import (
    _attach_counts_from_wdk_strategy,
    _build_snapshot_from_wdk,
    _normalize_synced_parameters,
)
from veupath_chatbot.transport.http.deps import (
    CurrentUser,
    StrategyRepo,
)
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.schemas import (
    MessageResponse,
    OpenStrategyRequest,
    OpenStrategyResponse,
    StepResponse,
    StrategyResponse,
    StrategySummaryResponse,
    ThinkingResponse,
    WdkStrategySummaryResponse,
)

from ._shared import build_step_response

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])
logger = get_logger(__name__)


async def _sync_single_wdk_strategy(
    *,
    wdk_id: int,
    site_id: str,
    api: StrategyAPI,
    strategy_repo: StrategyRepo,
    user_id: UUID,
) -> Strategy:
    """Fetch a single WDK strategy and upsert a local copy.

    Shared by ``open_strategy`` and ``sync_all_wdk_strategies``.
    """

    wdk_strategy = await api.get_strategy(wdk_id)

    ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)
    _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)

    # Read isSaved from the WDK payload so we mirror draft/saved state locally.
    is_saved_raw = (
        wdk_strategy.get("isSaved") if isinstance(wdk_strategy, dict) else None
    )
    is_saved = bool(is_saved_raw) if isinstance(is_saved_raw, bool) else False

    existing = await strategy_repo.get_by_wdk_strategy_id(user_id, wdk_id)
    if existing:
        updated = await strategy_repo.update(
            strategy_id=existing.id,
            name=ast.name or existing.name,
            plan=ast.to_dict(),
            record_type=ast.record_type,
            wdk_strategy_id=wdk_id,
            wdk_strategy_id_set=True,
            is_saved=is_saved,
            is_saved_set=True,
        )
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )
        return updated
    else:
        return await strategy_repo.create(
            user_id=user_id,
            name=ast.name or f"WDK Strategy {wdk_id}",
            site_id=site_id,
            record_type=ast.record_type,
            plan=ast.to_dict(),
            wdk_strategy_id=wdk_id,
            is_saved=is_saved,
        )


def _parse_wdk_strategy_id(item: JSONObject) -> int | None:
    """Extract integer WDK strategy ID from a list-strategies item.

    WDK's ``StrategyFormatter`` emits ``strategyId`` (``JsonKeys.STRATEGY_ID``)
    as a Java long (always an int in JSON).

    :param item: Item dict.

    """
    wdk_id = item.get("strategyId")
    if isinstance(wdk_id, int):
        return wdk_id
    return None


@router.post("/open", response_model=OpenStrategyResponse)
async def open_strategy(
    request: OpenStrategyRequest,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> OpenStrategyResponse:
    """Open a strategy by local or WDK strategy."""
    if not request.strategy_id and not request.wdk_strategy_id:
        if not request.site_id:
            raise ValidationError(
                detail="siteId is required",
                errors=[
                    {
                        "path": "siteId",
                        "message": "Required",
                        "code": "INVALID_PARAMETERS",
                    }
                ],
            )
        strategy = await strategy_repo.create(
            user_id=user_id,
            name="Draft Strategy",
            site_id=request.site_id,
            record_type=None,
            plan={},
        )
    elif request.strategy_id:
        strategy = await get_owned_strategy_or_404(
            strategy_repo, request.strategy_id, user_id
        )
    else:
        if not request.site_id:
            raise ValidationError(
                detail="siteId is required",
                errors=[
                    {
                        "path": "siteId",
                        "message": "Required",
                        "code": "INVALID_PARAMETERS",
                    }
                ],
            )
        if request.wdk_strategy_id is None:
            raise ValidationError(
                detail="wdk_strategy_id is required",
                errors=[
                    {
                        "path": "wdk_strategy_id",
                        "message": "Required",
                        "code": "INVALID_PARAMETERS",
                    }
                ],
            )
        try:
            api = get_strategy_api(request.site_id)
            strategy = await _sync_single_wdk_strategy(
                wdk_id=request.wdk_strategy_id,
                site_id=request.site_id,
                api=api,
                strategy_repo=strategy_repo,
                user_id=user_id,
            )
        except WDKError as e:
            logger.error("WDK fetch failed", error=str(e))
            raise
        except Exception as e:
            logger.error("WDK fetch failed", error=str(e))
            raise WDKError(f"Failed to load WDK strategy: {e}") from e

    return OpenStrategyResponse(
        strategyId=strategy.id,
    )


@router.get("/wdk", response_model=list[WdkStrategySummaryResponse])
async def list_wdk_strategies(
    site_id: Annotated[str | None, Query(alias="siteId")] = None,
) -> list[WdkStrategySummaryResponse]:
    """List strategies from VEuPathDB WDK."""
    sites = [get_site(site_id)] if site_id else list_sites()
    results: JSONArray = []

    for site in sites:
        try:
            api = get_strategy_api(site.id)
            strategies = await api.list_strategies()
            for item in strategies:
                if not isinstance(item, dict):
                    continue
                wdk_id_int = _parse_wdk_strategy_id(item)
                if wdk_id_int is None:
                    continue
                root_step_id_raw = item.get("rootStepId")
                root_step_id: int | None = (
                    root_step_id_raw if isinstance(root_step_id_raw, int) else None
                )
                # WDK emits JsonKeys.IS_SAVED = "isSaved" as a boolean.
                is_saved_raw = item.get("isSaved")
                is_saved: bool | None = (
                    bool(is_saved_raw) if isinstance(is_saved_raw, bool) else None
                )
                name_raw = item.get("name")
                name = (
                    name_raw
                    if isinstance(name_raw, str)
                    else f"WDK Strategy {wdk_id_int}"
                )
                is_internal = is_internal_wdk_strategy_name(name)
                if is_internal:
                    name = strip_internal_wdk_strategy_name(name)
                from veupath_chatbot.transport.http.schemas import (
                    WdkStrategySummaryResponse,
                )

                results.append(
                    cast(
                        JSONValue,
                        WdkStrategySummaryResponse(
                            wdkStrategyId=wdk_id_int,
                            name=name,
                            siteId=site.id,
                            wdkUrl=site.strategy_url(wdk_id_int, root_step_id),
                            rootStepId=root_step_id,
                            isSaved=is_saved,
                            isInternal=is_internal,
                        ).model_dump(),
                    )
                )
        except Exception as e:
            logger.warning("WDK strategy list failed", site_id=site.id, error=str(e))

    from veupath_chatbot.transport.http.schemas import WdkStrategySummaryResponse

    return [
        WdkStrategySummaryResponse.model_validate(r)
        if isinstance(r, dict)
        else WdkStrategySummaryResponse(
            wdkStrategyId=0,
            name="",
            siteId="",
            wdkUrl="",
            rootStepId=None,
            isSaved=None,
            isInternal=False,
        )
        for r in results
        if isinstance(r, dict)
    ]


@router.post("/sync-wdk", response_model=list[StrategySummaryResponse])
async def sync_all_wdk_strategies(
    site_id: Annotated[str, Query(alias="siteId")],
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> list[StrategySummaryResponse]:
    """Batch-sync all WDK strategies into the local DB and return the full list.

    For each non-internal WDK strategy, fetches the full payload and upserts
    a local copy. Returns the complete list of local strategies for this site
    (including non-WDK drafts).
    """
    from datetime import UTC, datetime

    site = get_site(site_id)
    try:
        api = get_strategy_api(site.id)
        wdk_items = await api.list_strategies()
    except Exception as e:
        logger.warning("WDK list failed during sync", site_id=site.id, error=str(e))
        wdk_items = []

    for item in wdk_items:
        if not isinstance(item, dict):
            continue
        wdk_id = _parse_wdk_strategy_id(item)
        if wdk_id is None:
            continue
        name_raw = item.get("name")
        name = name_raw if isinstance(name_raw, str) else ""
        if is_internal_wdk_strategy_name(name):
            continue
        try:
            await _sync_single_wdk_strategy(
                wdk_id=wdk_id,
                site_id=site.id,
                api=api,
                strategy_repo=strategy_repo,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to sync WDK strategy",
                wdk_id=wdk_id,
                site_id=site.id,
                error=str(e),
            )

    # Return the full local list (now includes all synced WDK strategies).
    strategies = await strategy_repo.list_by_user(user_id, site_id)
    return [
        StrategySummaryResponse(
            id=s.id,
            name=s.name,
            title=s.title,
            siteId=s.site_id,
            recordType=s.record_type,
            stepCount=(
                count_steps_in_plan(s.plan or {})
                or (len(s.steps or []) if s.steps else 0)
            ),
            resultCount=s.result_count,
            wdkStrategyId=s.wdk_strategy_id,
            isSaved=s.is_saved,
            createdAt=s.created_at or datetime.now(UTC),
            updatedAt=s.updated_at or datetime.now(UTC),
        )
        for s in strategies
    ]


@router.delete("/wdk/{wdkStrategyId}", status_code=204, response_class=Response)
async def delete_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
) -> Response:
    """Delete a strategy from VEuPathDB WDK."""
    try:
        api = get_strategy_api(siteId)
        await api.delete_strategy(wdkStrategyId)
    except Exception as e:
        logger.error("WDK strategy delete failed", error=str(e))
        raise WDKError("Failed to delete strategy from VEuPathDB") from e
    return Response(status_code=204)


@router.post("/wdk/{wdkStrategyId}/import", response_model=StrategyResponse)
async def import_wdk_strategy(
    wdkStrategyId: int,
    siteId: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StrategyResponse:
    """Import a WDK strategy as a local snapshot."""
    try:
        api = get_strategy_api(siteId)
        wdk_strategy = await api.get_strategy(wdkStrategyId)

        ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)

        # Mirror isSaved from the WDK payload.
        is_saved_raw = (
            wdk_strategy.get("isSaved") if isinstance(wdk_strategy, dict) else None
        )
        is_saved = bool(is_saved_raw) if isinstance(is_saved_raw, bool) else False

        created = await strategy_repo.create(
            user_id=user_id,
            name=ast.name or f"WDK Strategy {wdkStrategyId}",
            title=ast.name or f"WDK Strategy {wdkStrategyId}",
            site_id=siteId,
            record_type=ast.record_type,
            plan=ast.to_dict(),
            wdk_strategy_id=wdkStrategyId,
            is_saved=is_saved,
        )

        plan_dict: JSONObject = created.plan if isinstance(created.plan, dict) else {}
        metadata_raw = plan_dict.get("metadata")
        metadata: JSONObject = metadata_raw if isinstance(metadata_raw, dict) else {}
        description_raw = metadata.get("description")
        description: str | None = (
            description_raw if isinstance(description_raw, str) else None
        )

        steps_responses: list[StepResponse] = []
        for s in steps_data:
            if isinstance(s, dict):
                steps_responses.append(build_step_response(s))

        from veupath_chatbot.transport.http.schemas import (
            MessageResponse,
            ThinkingResponse,
        )

        messages_list: list[MessageResponse] | None = None
        if created.messages:
            messages_list = [
                MessageResponse.model_validate(m)
                if isinstance(m, dict)
                else MessageResponse(role="user", content="")
                for m in created.messages
                if isinstance(m, dict)
            ]

        thinking_obj: ThinkingResponse | None = None
        if isinstance(created.thinking, dict):
            thinking_obj = ThinkingResponse.model_validate(created.thinking)

        return StrategyResponse(
            id=created.id,
            name=created.name,
            title=created.title,
            description=description,
            siteId=created.site_id,
            recordType=created.record_type,
            steps=steps_responses,
            rootStepId=ast.root.id,
            wdkStrategyId=created.wdk_strategy_id,
            isSaved=created.is_saved,
            messages=messages_list,
            thinking=thinking_obj,
            modelId=created.model_id,
            createdAt=created.created_at,
            updatedAt=created.updated_at,
        )
    except AppError:
        raise
    except WDKError as e:
        # Preserve upstream status/detail for debugging (e.g. permission denied).
        logger.error("WDK import failed", error=str(e))
        raise
    except Exception as e:
        logger.error("WDK import failed", error=str(e))
        raise WDKError(f"Failed to import strategy from WDK: {e}") from e


@router.post("/{strategyId:uuid}/sync-wdk", response_model=StrategyResponse)
async def sync_strategy_from_wdk(
    strategyId: UUID,
    strategy_repo: StrategyRepo,
) -> StrategyResponse:
    """Sync local strategy snapshot from VEuPathDB WDK."""
    strategy = await strategy_repo.get_by_id(strategyId)
    if not strategy:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
        )
    if not strategy.wdk_strategy_id:
        raise ValidationError(
            detail="Strategy not linked to WDK",
            errors=[
                {
                    "path": "wdkStrategyId",
                    "message": "Strategy must be linked to WDK",
                    "code": "INVALID_STRATEGY",
                }
            ],
        )

    try:
        api = get_strategy_api(strategy.site_id)
        wdk_strategy = await api.get_strategy(strategy.wdk_strategy_id)

        ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)
        await _normalize_synced_parameters(ast, steps_data, api)
        _attach_counts_from_wdk_strategy(steps_data, wdk_strategy)
        ast.name = ast.name or strategy.name

        # Mirror isSaved from the WDK payload.
        is_saved_raw = (
            wdk_strategy.get("isSaved") if isinstance(wdk_strategy, dict) else None
        )
        is_saved = bool(is_saved_raw) if isinstance(is_saved_raw, bool) else False

        updated = await strategy_repo.update(
            strategy_id=strategyId,
            name=ast.name or strategy.name,
            plan=ast.to_dict(),
            is_saved=is_saved,
            is_saved_set=True,
        )
        if not updated:
            raise NotFoundError(
                code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found"
            )

        plan_dict: JSONObject = updated.plan if isinstance(updated.plan, dict) else {}
        metadata_raw = plan_dict.get("metadata")
        metadata: JSONObject = metadata_raw if isinstance(metadata_raw, dict) else {}
        description_raw = metadata.get("description")
        description: str | None = (
            description_raw if isinstance(description_raw, str) else None
        )

        steps_responses: list[StepResponse] = []
        for s in steps_data:
            if isinstance(s, dict):
                steps_responses.append(build_step_response(s))

        return StrategyResponse(
            id=updated.id,
            name=updated.name,
            description=description,
            siteId=updated.site_id,
            recordType=updated.record_type,
            steps=steps_responses,
            rootStepId=ast.root.id,
            wdkStrategyId=updated.wdk_strategy_id,
            isSaved=updated.is_saved,
            modelId=updated.model_id,
            createdAt=updated.created_at,
            updatedAt=updated.updated_at,
        )
    except AppError:
        raise
    except WDKError as e:
        logger.error("WDK sync failed", error=str(e))
        raise
    except Exception as e:
        logger.error("WDK sync failed", error=str(e))
        raise WDKError(f"Failed to sync strategy from WDK: {e}") from e
