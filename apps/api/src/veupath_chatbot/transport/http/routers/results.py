"""Result preview and download endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from veupath_chatbot.platform.errors import ErrorCode, NotFoundError, ValidationError, WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.transport.http.deps import StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_strategy_or_404
from veupath_chatbot.integrations.veupathdb.factory import get_results_api
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.schemas import (
    DownloadRequest,
    DownloadResponse,
    PreviewRequest,
    PreviewResponse,
)

router = APIRouter(prefix="/api/v1/results", tags=["results"])
logger = get_logger(__name__)


@router.post("/preview", response_model=PreviewResponse)
async def preview_results(
    request: PreviewRequest,
    strategy_repo: StrategyRepo,
):
    """Preview step results.

    Returns a sample of records and total count for the specified step.
    The strategy must have been pushed to WDK first.
    """
    strategy = await get_strategy_or_404(strategy_repo, request.strategy_id)

    if not strategy.wdk_strategy_id:
        raise ValidationError(
            detail="Strategy must be pushed to WDK first",
            errors=[
                {
                    "path": "wdkStrategyId",
                    "message": "Strategy must be pushed to WDK first",
                    "code": "INVALID_STRATEGY",
                }
            ],
        )

    # Find the step
    step_data = None
    steps = build_steps_data_from_plan(strategy.plan or {})
    for s in steps:
        if s.get("id") == request.step_id:
            step_data = s
            break

    if not step_data:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    try:
        results_api = get_results_api(strategy.site_id)

        wdk_step_id = step_data.get("wdkStepId") or strategy.wdk_strategy_id
        if not wdk_step_id:
            raise ValidationError(
                detail="Step is not linked to a WDK step yet",
                errors=[
                    {
                        "path": "steps[].wdkStepId",
                        "message": "Step must be linked to WDK",
                        "code": "INVALID_STRATEGY",
                    }
                ],
            )

        # Get preview
        preview = await results_api.get_step_preview(
            step_id=wdk_step_id,
            limit=request.limit,
        )

        records = preview.get("records", [])
        meta = preview.get("meta", {})

        return PreviewResponse(
            totalCount=meta.get("totalCount", len(records)),
            records=records,
            columns=list(records[0].keys()) if records else [],
        )

    except Exception as e:
        logger.error("Preview failed", error=str(e))
        raise WDKError(f"Preview error: {e}")


@router.post("/download", response_model=DownloadResponse)
async def download_results(
    request: DownloadRequest,
    strategy_repo: StrategyRepo,
):
    """Get download URL for step results.

    Creates a temporary result on VEuPathDB and returns a download URL.
    """
    strategy = await get_strategy_or_404(strategy_repo, request.strategy_id)

    if not strategy.wdk_strategy_id:
        raise ValidationError(
            detail="Strategy must be pushed to WDK first",
            errors=[
                {
                    "path": "wdkStrategyId",
                    "message": "Strategy must be pushed to WDK first",
                    "code": "INVALID_STRATEGY",
                }
            ],
        )

    try:
        results_api = get_results_api(strategy.site_id)

        wdk_step_id = None
        steps = build_steps_data_from_plan(strategy.plan or {})
        for s in steps:
            if s.get("id") == request.step_id:
                wdk_step_id = s.get("wdkStepId") or strategy.wdk_strategy_id
                break
        if not wdk_step_id:
            raise ValidationError(
                detail="Step is not linked to a WDK step yet",
                errors=[
                    {
                        "path": "steps[].wdkStepId",
                        "message": "Step must be linked to WDK",
                        "code": "INVALID_STRATEGY",
                    }
                ],
            )

        download_url = await results_api.get_download_url(
            step_id=wdk_step_id,
            format=request.format,
            attributes=request.attributes,
        )

        return DownloadResponse(
            downloadUrl=download_url,
            expiresAt=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    except Exception as e:
        logger.error("Download failed", error=str(e))
        raise WDKError(f"Download error: {e}")

