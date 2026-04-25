"""Result and download response models and helpers."""

from __future__ import annotations

from pydantic import Field
from pydantic_ai.exceptions import ModelRetry

from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
from pathfinder.platform.types import JSONObject
from pathfinder.services.wdk import StrategyAPI, TemporaryResultsAPI, WDKAnswer


class EstimatedSizeResult(CamelModel):
    """Result of a step size estimation."""

    step_id: int
    count: int


class DownloadUrlResult(CamelModel):
    """Result containing a download URL."""

    download_url: str
    format: str
    step_id: int


class SampleRecordsResult(CamelModel):
    """Sample records from a step."""

    step_id: int
    total_count: int
    records: list[JSONObject] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)


_MAX_SAMPLE_LIMIT = 100


def _validate_download_url_inputs(
    wdk_step_id: int,
    output_format: str,
) -> None:
    """Validate inputs for get_download_url. Raises ModelRetry on bad input."""
    valid_formats = {"csv", "tab", "json"}
    if output_format not in valid_formats:
        msg = (
            f"VALIDATION_ERROR: Invalid output_format {output_format!r}. "
            f"Must be one of: {', '.join(sorted(valid_formats))}."
        )
        raise ModelRetry(msg)
    if wdk_step_id <= 0:
        msg = (
            f"VALIDATION_ERROR: wdk_step_id must be a positive integer "
            f"(got {wdk_step_id})."
        )
        raise ModelRetry(msg)


def _validate_sample_inputs(
    wdk_step_id: int,
    limit: int,
) -> None:
    """Validate inputs for get_sample_records. Raises ModelRetry on bad input."""
    if wdk_step_id <= 0:
        msg = (
            f"VALIDATION_ERROR: wdk_step_id must be a positive integer "
            f"(got {wdk_step_id})."
        )
        raise ModelRetry(msg)
    if limit < 1 or limit > _MAX_SAMPLE_LIMIT:
        msg = (
            f"VALIDATION_ERROR: limit must be between 1 and 100 (got {limit})."
        )
        raise ModelRetry(msg)


async def _fetch_download_url(
    results_api: TemporaryResultsAPI,
    wdk_step_id: int,
    output_format: str,
    attributes: list[str] | None,
) -> str | ToolErrorPayload:
    """Fetch a download URL from the results API."""
    try:
        url: str = await results_api.get_download_url(
            wdk_step_id,
            output_format=output_format,
            attributes=attributes,
        )
    except (AppError, OSError) as e:
        return tool_error(ErrorCode.WDK_ERROR, str(e))
    else:
        return url


async def _fetch_step_preview(
    strategy_api: StrategyAPI,
    wdk_step_id: int,
    limit: int,
) -> WDKAnswer | ToolErrorPayload:
    """Fetch a step preview from the strategy API."""
    try:
        return await strategy_api.get_step_answer(
            wdk_step_id,
            pagination={"offset": 0, "numRecords": limit},
        )
    except (AppError, OSError) as e:
        return tool_error(ErrorCode.WDK_ERROR, str(e))


def _extract_sample_response(answer: WDKAnswer, wdk_step_id: int = 0) -> SampleRecordsResult:
    """Extract sample records from a WDK answer response."""
    records: list[JSONObject] = []
    total_count = answer.meta.total_count or 0
    attributes = list(answer.meta.attributes or [])

    for rec in answer.records:
        row: JSONObject = {"id": rec.display_name}
        for attr_name, attr_val in rec.attributes.items():
            row[attr_name] = attr_val
        records.append(row)

    return SampleRecordsResult(
        step_id=wdk_step_id,
        total_count=total_count,
        records=records,
        attributes=attributes,
    )
