"""VEuPathDB /temporary-results helpers for downloads."""

import asyncio
from typing import cast

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


class TemporaryResultsAPI:
    """API for creating and managing temporary result downloads."""

    def __init__(self, client: VEuPathDBClient) -> None:
        self.client = client
        self._session_initialized = False

    async def _ensure_session(self) -> None:
        """Initialize session cookies for the current user."""
        if self._session_initialized:
            return
        await self.client.get("/users/current")
        self._session_initialized = True

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
            JSONObject, await self.client.post("/temporary-results", json=payload)
        )

    async def get_temporary_result(self, result_id: str) -> JSONObject:
        """Get status of a temporary result."""
        await self._ensure_session()
        return cast(
            JSONObject, await self.client.get(f"/temporary-results/{result_id}")
        )

    async def get_download_url(
        self,
        step_id: int,
        format: str = "csv",
        attributes: list[str] | None = None,
    ) -> str:
        """Get download URL for step results.

        :param step_id: Step ID.
        :param format: Output format (csv, tab, json).
        :param attributes: Attributes to include.
        :returns: Download URL.
        """
        format_config: JSONObject = {}

        if format == "csv" or format == "tab":
            format_config["type"] = "standard"
            format_config["includeHeader"] = True
            format_config["attachmentType"] = "text"
        elif format == "json":
            format_config["type"] = "json"

        if attributes:
            # list[str] is compatible with JSONValue (JSONArray)
            format_config["attributes"] = cast(JSONArray, attributes)

        result = await self.create_temporary_result(
            step_id=step_id,
            reporter="standard" if format in ("csv", "tab") else "fullRecord",
            format_config=format_config,
        )
        url = self._extract_download_url(result)
        if url:
            return url

        # Some WDK deployments return an ID first, then populate the URL on
        # subsequent GET /temporary-results/{id}. Poll briefly before failing.
        result_id_raw = result.get("id") or result.get("resultId")
        result_id = str(result_id_raw) if result_id_raw is not None else ""
        if not result_id:
            raise RuntimeError(
                "VEuPathDB temporary-results response did not include either a "
                "download URL or a temporary result id."
            )

        last_status = "unknown"
        for _ in range(8):
            await asyncio.sleep(0.5)
            latest = await self.get_temporary_result(result_id)
            url = self._extract_download_url(latest)
            if url:
                return url
            status_raw = latest.get("status") or latest.get("state")
            if isinstance(status_raw, str) and status_raw:
                last_status = status_raw

        raise RuntimeError(
            f"Temporary result {result_id} did not produce a download URL "
            f"(last status: {last_status})."
        )

    @staticmethod
    def _extract_download_url(payload: JSONObject) -> str:
        """Extract a download URL across known WDK response shapes."""
        direct = (
            payload.get("url")
            or payload.get("downloadUrl")
            or payload.get("download_url")
        )
        if isinstance(direct, str) and direct.strip():
            return direct
        links_raw = payload.get("links")
        if isinstance(links_raw, dict):
            links_url = links_raw.get("download") or links_raw.get("url")
            if isinstance(links_url, str) and links_url.strip():
                return links_url
        return ""

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
            report_config["attributes"] = cast(JSONArray, attributes)

        # Use standard report endpoint for preview.
        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/current/steps/{step_id}/reports/standard",
                json={"reportConfig": report_config},
            ),
        )
