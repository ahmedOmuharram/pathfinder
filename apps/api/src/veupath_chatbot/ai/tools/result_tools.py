"""Tools for retrieving step results (sample records, download URLs)."""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.wdk_error_handler import handle_wdk_step_error
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKAnswer
from veupath_chatbot.platform.errors import AppError, ErrorCode, WDKError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.wdk import (
    StrategyAPI,
    TemporaryResultsAPI,
    get_results_api,
    get_strategy_api,
)

_MAX_SAMPLE_LIMIT = 500


class ResultTools:
    """Tools for fetching step results from VEuPathDB."""

    def __init__(
        self,
        session: StrategySession,
        strategy_api: StrategyAPI | None = None,
        results_api: TemporaryResultsAPI | None = None,
    ) -> None:
        self.session = session
        self.strategy_api = strategy_api
        self.results_api = results_api

    @ai_function()
    async def get_download_url(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        *,
        output_format: Annotated[
            str,
            AIParam(desc="Download format: csv, tab, or json"),
        ] = "csv",
        attributes: Annotated[
            list[str] | None,
            AIParam(desc="Specific attributes to include"),
        ] = None,
    ) -> JSONObject:
        """Get a download URL for step results.

        The URL can be used to download results in the specified format.
        """
        validation_error = _validate_download_url_inputs(
            wdk_step_id, output_format, attributes
        )
        if validation_error is not None:
            return validation_error

        url_or_error = await _fetch_download_url(
            self.results_api or get_results_api(self.session.site_id),
            wdk_step_id,
            output_format,
            attributes,
        )
        if (
            isinstance(url_or_error, dict)
            or not isinstance(url_or_error, str)
            or not url_or_error
        ):
            return (
                url_or_error
                if isinstance(url_or_error, dict)
                else tool_error(
                    ErrorCode.WDK_ERROR,
                    "VEuPathDB did not provide a usable download URL for this step. "
                    "This usually means the temporary result is still being prepared "
                    "or the upstream payload shape changed.",
                    wdk_step_id=wdk_step_id,
                    output_format=output_format,
                )
            )
        return {
            "downloadUrl": url_or_error,
            "format": output_format,
            "stepId": wdk_step_id,
        }

    @ai_function()
    async def get_sample_records(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        limit: Annotated[int, AIParam(desc="Number of records")] = 5,
    ) -> JSONObject:
        """Get a sample of records from an executed step.

        Returns the first N records to show the user what data is available.
        """
        validation_error = _validate_sample_inputs(wdk_step_id, limit)
        if validation_error is not None:
            return validation_error

        preview_or_error = await _fetch_step_preview(
            self.strategy_api or get_strategy_api(self.session.site_id),
            wdk_step_id,
            limit,
        )
        if isinstance(preview_or_error, dict):
            # Error payload from exception handler
            return preview_or_error
        return _extract_sample_response(preview_or_error)


def _validate_download_url_inputs(
    wdk_step_id: int,
    output_format: str,
    attributes: list[str] | None,
) -> JSONObject | None:
    """Validate all inputs for get_download_url. Returns error payload or None."""
    err = _validate_step_id(wdk_step_id) or _validate_download_format(output_format)
    if err is not None:
        return err
    return _validate_attributes(attributes) if attributes is not None else None


async def _fetch_download_url(
    results_api: TemporaryResultsAPI,
    wdk_step_id: int,
    output_format: str,
    attributes: list[str] | None,
) -> str | JSONObject:
    """Fetch download URL from VEuPathDB. Returns URL string or error payload dict."""
    try:
        return await results_api.get_download_url(
            step_id=wdk_step_id,
            output_format=output_format,
            attributes=attributes,
        )
    except WDKError as e:
        return handle_wdk_step_error(
            e,
            wdk_step_id=wdk_step_id,
            action="download",
            fallback_message="generating the download URL",
        )
    except (AppError, OSError) as e:
        return tool_error(
            ErrorCode.WDK_ERROR,
            "Failed to generate download URL from VEuPathDB.",
            wdk_step_id=wdk_step_id,
            detail=str(e),
        )


def _validate_sample_inputs(wdk_step_id: int, limit: int) -> JSONObject | None:
    """Validate inputs for get_sample_records. Returns error payload or None."""
    err = _validate_step_id(wdk_step_id)
    if err is not None:
        return err
    if not isinstance(limit, int) or limit < 1 or limit > _MAX_SAMPLE_LIMIT:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            f"limit must be an integer between 1 and {_MAX_SAMPLE_LIMIT}.",
            limit=limit,
            min=1,
            max=_MAX_SAMPLE_LIMIT,
        )
    return None


async def _fetch_step_preview(
    strategy_api: StrategyAPI,
    wdk_step_id: int,
    limit: int,
) -> WDKAnswer | JSONObject:
    """Fetch step answer from VEuPathDB. Returns typed answer or error payload dict."""
    try:
        return await strategy_api.get_step_answer(
            step_id=wdk_step_id,
            pagination={"offset": 0, "numRecords": limit},
        )
    except WDKError as e:
        return handle_wdk_step_error(
            e,
            wdk_step_id=wdk_step_id,
            action="read",
            fallback_message="reading step records",
        )
    except (AppError, OSError) as e:
        return tool_error(
            ErrorCode.WDK_ERROR,
            "Failed to fetch sample records from VEuPathDB.",
            wdk_step_id=wdk_step_id,
            detail=str(e),
        )


def _validate_step_id(wdk_step_id: int) -> JSONObject | None:
    if not isinstance(wdk_step_id, int) or wdk_step_id <= 0:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "wdk_step_id must be a positive integer.",
            wdk_step_id=wdk_step_id,
            expected="positive integer",
        )
    return None


def _validate_download_format(output_format: str) -> JSONObject | None:
    if output_format not in {"csv", "tab", "json"}:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "format must be one of: csv, tab, json.",
            output_format=output_format,
            allowed=["csv", "tab", "json"],
        )
    return None


def _validate_attributes(attributes: list[str]) -> JSONObject | None:
    if len(attributes) == 0:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "attributes cannot be an empty list when provided.",
            attributes=cast("JSONValue", attributes),
        )
    bad_attrs = [a for a in attributes if not isinstance(a, str) or not a.strip()]
    if bad_attrs:
        return tool_error(
            ErrorCode.VALIDATION_ERROR,
            "attributes must contain non-empty strings.",
            invalidAttributes=cast("JSONValue", bad_attrs),
        )
    return None


def _extract_sample_response(answer: WDKAnswer) -> JSONObject:
    records = answer.records
    total_count = answer.meta.total_count
    attributes_list: list[str] = []
    if records:
        attributes_list = list(records[0].attributes.keys())
    attributes: JSONValue = cast("JSONValue", attributes_list)
    return {
        "records": cast("JSONValue", [r.model_dump(by_alias=True) for r in records]),
        "totalCount": total_count,
        "attributes": attributes,
    }
