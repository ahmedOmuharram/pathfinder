"""Tools for retrieving step results (sample records, download URLs)."""

from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.wdk_error_handler import handle_wdk_step_error
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.factory import (
    get_results_api,
    get_strategy_api,
)
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.platform.errors import ErrorCode, WDKError
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONObject, JSONValue


class ResultTools:
    """Tools for fetching step results from VEuPathDB."""

    def __init__(self, session: StrategySession) -> None:
        self.session = session

    def _get_api(self) -> StrategyAPI:
        return get_strategy_api(self.session.site_id)

    def _get_results_api(self) -> TemporaryResultsAPI:
        return get_results_api(self.session.site_id)

    @ai_function()
    async def get_download_url(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        format: Annotated[
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
        if not isinstance(wdk_step_id, int) or wdk_step_id <= 0:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "wdk_step_id must be a positive integer.",
                wdk_step_id=wdk_step_id,
                expected="positive integer",
            )
        if format not in {"csv", "tab", "json"}:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "format must be one of: csv, tab, json.",
                format=format,
                allowed=["csv", "tab", "json"],
            )
        if attributes is not None:
            if len(attributes) == 0:
                return tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "attributes cannot be an empty list when provided.",
                    attributes=cast(JSONValue, attributes),
                )
            bad_attrs = [
                a for a in attributes if not isinstance(a, str) or not a.strip()
            ]
            if bad_attrs:
                return tool_error(
                    ErrorCode.VALIDATION_ERROR,
                    "attributes must contain non-empty strings.",
                    invalidAttributes=cast(JSONValue, bad_attrs),
                )

        try:
            results_api = self._get_results_api()
            url = await results_api.get_download_url(
                step_id=wdk_step_id,
                format=format,
                attributes=attributes,
            )
            if not isinstance(url, str) or not url:
                return tool_error(
                    ErrorCode.WDK_ERROR,
                    "VEuPathDB did not provide a usable download URL for this step. "
                    "This usually means the temporary result is still being prepared "
                    "or the upstream payload shape changed.",
                    wdk_step_id=wdk_step_id,
                    format=format,
                )
            return {
                "downloadUrl": url,
                "format": format,
                "stepId": wdk_step_id,
            }
        except WDKError as e:
            return handle_wdk_step_error(
                e,
                wdk_step_id=wdk_step_id,
                action="download",
                fallback_message="generating the download URL",
            )
        except Exception as e:
            return tool_error(
                ErrorCode.WDK_ERROR,
                "Failed to generate download URL from VEuPathDB.",
                wdk_step_id=wdk_step_id,
                detail=str(e),
            )

    @ai_function()
    async def get_sample_records(
        self,
        wdk_step_id: Annotated[int, AIParam(desc="WDK step ID")],
        limit: Annotated[int, AIParam(desc="Number of records")] = 5,
    ) -> JSONObject:
        """Get a sample of records from an executed step.

        Returns the first N records to show the user what data is available.
        """
        if not isinstance(wdk_step_id, int) or wdk_step_id <= 0:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "wdk_step_id must be a positive integer.",
                wdk_step_id=wdk_step_id,
                expected="positive integer",
            )
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            return tool_error(
                ErrorCode.VALIDATION_ERROR,
                "limit must be an integer between 1 and 500.",
                limit=limit,
                min=1,
                max=500,
            )

        try:
            strategy_api = self._get_api()
            preview_raw = await strategy_api.get_step_answer(
                step_id=wdk_step_id,
                pagination={"offset": 0, "numRecords": limit},
            )
            if not isinstance(preview_raw, dict):
                raise TypeError("Expected dict from get_step_preview")
            preview: dict[str, JSONValue] = {str(k): v for k, v in preview_raw.items()}
            records_raw = preview.get("records", [])
            records: list[JSONValue] = (
                records_raw if isinstance(records_raw, list) else []
            )
            meta_raw = preview.get("meta", {})
            meta: dict[str, JSONValue] = meta_raw if isinstance(meta_raw, dict) else {}
            total_count_raw = meta.get("totalCount", 0)
            total_count: int = (
                total_count_raw if isinstance(total_count_raw, int) else 0
            )
            attributes_list: list[str] = []
            if records and isinstance(records[0], dict):
                attributes_list = [str(k) for k in records[0]]
            attributes: JSONValue = cast(JSONValue, attributes_list)
            return {
                "records": records,
                "totalCount": total_count,
                "attributes": attributes,
            }
        except WDKError as e:
            return handle_wdk_step_error(
                e,
                wdk_step_id=wdk_step_id,
                action="read",
                fallback_message="reading step records",
            )
        except Exception as e:
            return tool_error(
                ErrorCode.WDK_ERROR,
                "Failed to fetch sample records from VEuPathDB.",
                wdk_step_id=wdk_step_id,
                detail=str(e),
            )
