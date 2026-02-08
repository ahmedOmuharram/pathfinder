"""Result preview and download endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from veupath_chatbot.integrations.veupathdb.factory import get_results_api
from veupath_chatbot.platform.errors import (
    ErrorCode,
    NotFoundError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_strategy_or_404
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
) -> PreviewResponse:
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
    step_data: JSONObject | None = None
    steps = build_steps_data_from_plan(strategy.plan or {})
    for s in steps:
        if isinstance(s, dict):
            step_id_value = s.get("id")
            if step_id_value == request.step_id:
                step_data = s
                break

    if not step_data:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")

    try:
        results_api = get_results_api(strategy.site_id)

        wdk_step_id_raw = step_data.get("wdkStepId") or strategy.wdk_strategy_id
        if not wdk_step_id_raw:
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

        # Ensure wdk_step_id is an int
        wdk_step_id: int
        if isinstance(wdk_step_id_raw, int):
            wdk_step_id = wdk_step_id_raw
        elif isinstance(wdk_step_id_raw, str):
            try:
                wdk_step_id = int(wdk_step_id_raw)
            except ValueError as err:
                raise ValidationError(
                    detail="Invalid wdkStepId format",
                    errors=[
                        {
                            "path": "steps[].wdkStepId",
                            "message": "wdkStepId must be an integer",
                            "code": "INVALID_STRATEGY",
                        }
                    ],
                ) from err
        else:
            raise ValidationError(
                detail="Invalid wdkStepId type",
                errors=[
                    {
                        "path": "steps[].wdkStepId",
                        "message": "wdkStepId must be an integer",
                        "code": "INVALID_STRATEGY",
                    }
                ],
            )

        # Get preview
        preview = await results_api.get_step_preview(
            step_id=wdk_step_id,
            limit=request.limit,
        )

        if not isinstance(preview, dict):
            raise WDKError("Invalid preview response format")

        records_raw = preview.get("records", [])
        records: JSONArray = records_raw if isinstance(records_raw, list) else []
        meta_raw = preview.get("meta", {})
        meta: JSONObject = meta_raw if isinstance(meta_raw, dict) else {}

        total_count_raw = meta.get("totalCount")
        total_count: int
        if isinstance(total_count_raw, int):
            total_count = total_count_raw
        elif isinstance(total_count_raw, str):
            try:
                total_count = int(total_count_raw)
            except ValueError:
                total_count = len(records)
        else:
            total_count = len(records)

        columns: list[str] = []
        if records and isinstance(records[0], dict):
            columns = list(records[0].keys())

        return PreviewResponse(
            totalCount=total_count,
            records=records,
            columns=columns,
        )

    except Exception as e:
        logger.error("Preview failed", error=str(e))
        raise WDKError(f"Preview error: {e}") from e


@router.post("/download", response_model=DownloadResponse)
async def download_results(
    request: DownloadRequest,
    strategy_repo: StrategyRepo,
) -> DownloadResponse:
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

        wdk_step_id_raw: int | str | None = None
        steps = build_steps_data_from_plan(strategy.plan or {})
        for s in steps:
            if isinstance(s, dict):
                step_id_value = s.get("id")
                if step_id_value == request.step_id:
                    wdk_step_id_value = s.get("wdkStepId")
                    if wdk_step_id_value is not None:
                        if isinstance(wdk_step_id_value, (int, str)):
                            wdk_step_id_raw = wdk_step_id_value
                        else:
                            wdk_step_id_raw = None
                    elif strategy.wdk_strategy_id is not None:
                        wdk_step_id_raw = strategy.wdk_strategy_id
                    else:
                        wdk_step_id_raw = None
                    break

        if not wdk_step_id_raw:
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

        # Ensure wdk_step_id is an int
        wdk_step_id: int
        if isinstance(wdk_step_id_raw, int):
            wdk_step_id = wdk_step_id_raw
        elif isinstance(wdk_step_id_raw, str):
            try:
                wdk_step_id = int(wdk_step_id_raw)
            except ValueError as err:
                raise ValidationError(
                    detail="Invalid wdkStepId format",
                    errors=[
                        {
                            "path": "steps[].wdkStepId",
                            "message": "wdkStepId must be an integer",
                            "code": "INVALID_STRATEGY",
                        }
                    ],
                ) from err
        else:
            raise ValidationError(
                detail="Invalid wdkStepId type",
                errors=[
                    {
                        "path": "steps[].wdkStepId",
                        "message": "wdkStepId must be an integer",
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
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
        )

    except Exception as e:
        logger.error("Download failed", error=str(e))
        raise WDKError(f"Download error: {e}") from e
