"""Result and download response models and helpers."""

from __future__ import annotations

from pydantic import Field

from veupath_chatbot.integrations.veupathdb.strategy_api.api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKAnswer
from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.tool_errors import ToolErrorPayload, tool_error
from veupath_chatbot.platform.types import JSONObject


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
    attributes: list[str] | None,
) -> ToolErrorPayload | None:
    """Validate inputs for get_download_url."""
    valid_formats = {"csv", "tab", "json"}
    if output_format not in valid_formats:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            f"Invalid output_format '{output_format}'. Must be one of: {', '.join(sorted(valid_formats))}",
        )
    if wdk_step_id <= 0:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "wdk_step_id must be a positive integer.",
        )
    return None


def _validate_sample_inputs(
    wdk_step_id: int,
    limit: int,
) -> ToolErrorPayload | None:
    """Validate inputs for get_sample_records."""
    if wdk_step_id <= 0:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "wdk_step_id must be a positive integer.",
        )
    if limit < 1 or limit > _MAX_SAMPLE_LIMIT:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "limit must be between 1 and 100.",
        )
    return None


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
