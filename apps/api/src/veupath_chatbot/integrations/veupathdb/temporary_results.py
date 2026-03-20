"""VEuPathDB /temporary-results helpers for downloads."""

from typing import cast

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


class TemporaryResultsAPI(StrategyAPIBase):
    """API for creating and managing temporary result downloads.

    Inherits session management (``client``, ``user_id``, ``_ensure_session``)
    from :class:`StrategyAPIBase`.
    """

    async def create_temporary_result(
        self,
        step_id: int,
        reporter: str = "standard",
        format_config: JSONObject | None = None,
    ) -> JSONObject:
        """Create a temporary result for download.

        :param step_id: Step ID to export.
        :param reporter: WDK reporter name (standard, fullRecord, etc.).
        :param format_config: Reporter-specific configuration.
        :returns: Temporary result info with ID and download URL.
        """
        payload: JSONObject = {
            "stepId": step_id,
            # WDK expects "reportName" here; using "reporterName" triggers
            # 400: JSONObject["reportName"] not found.
            "reportName": reporter,
        }
        if format_config:
            payload["reportConfig"] = format_config

        logger.info(
            "Creating temporary result",
            step_id=step_id,
            reporter=reporter,
        )

        await self._ensure_session()
        return cast(
            "JSONObject", await self.client.post("/temporary-results", json=payload)
        )

    async def get_temporary_result(self, result_id: str) -> JSONObject:
        """Get status of a temporary result."""
        await self._ensure_session()
        return cast(
            "JSONObject", await self.client.get(f"/temporary-results/{result_id}")
        )

    async def get_download_url(
        self,
        step_id: int,
        output_format: str = "csv",
        attributes: list[str] | None = None,
    ) -> str:
        """Get download URL for step results.

        Creates a temporary result via POST, extracts the ``id`` from the
        response, and constructs the download URL:
        ``{base_url}/temporary-results/{id}/result``.

        :param step_id: Step ID.
        :param output_format: Output format (csv, tab, json).
        :param attributes: Attributes to include.
        :returns: Download URL.
        """
        format_config: JSONObject = {}

        if output_format in {"csv", "tab"}:
            format_config["type"] = "standard"
            format_config["includeHeader"] = True
            format_config["attachmentType"] = "text"
        elif output_format == "json":
            format_config["type"] = "json"

        if attributes:
            # list[str] is compatible with JSONValue (JSONArray)
            format_config["attributes"] = cast("JSONArray", attributes)

        result = await self.create_temporary_result(
            step_id=step_id,
            reporter="standard" if output_format in ("csv", "tab") else "fullRecord",
            format_config=format_config,
        )

        result_id_raw = result.get("id")
        if result_id_raw is None:
            msg = "VEuPathDB temporary-results response did not include an id."
            raise RuntimeError(msg)
        result_id = str(result_id_raw)

        base = self.client.base_url.rstrip("/")
        return f"{base}/temporary-results/{result_id}"

    async def get_step_preview(
        self,
        step_id: int,
        limit: int = 100,
        attributes: list[str] | None = None,
    ) -> JSONObject:
        """Get preview of step results.

        :param step_id: Step ID.
        :param limit: Max records to return.
        :param attributes: Attributes to include.
        :returns: Preview data with records.
        """
        report_config: JSONObject = {
            "pagination": {
                "offset": 0,
                "numRecords": limit,
            }
        }
        if attributes:
            report_config["attributes"] = cast("JSONArray", attributes)

        await self._ensure_session()
        return await self._standard_report(step_id, report_config)
