"""VEuPathDB /temporary-results helpers for downloads."""

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
        reporter: str = "tabular",
        format_config: JSONObject | None = None,
    ) -> JSONObject:
        """Create a temporary result for download.

        :param step_id: Step ID to export.
        :param reporter: Reporter type (tabular, fullRecord, etc.).
        :param format_config: Reporter-specific configuration.
        :returns: Temporary result info with ID and download URL.
        """
        payload: JSONObject = {
            "stepId": step_id,
            "reporterName": reporter,
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
            reporter="tabular" if format in ("csv", "tab") else "fullRecordJson",
            format_config=format_config,
        )

        return cast(str, result.get("url", ""))

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
        params: JSONObject = {
            "numRecords": limit,
            "offset": 0,
        }
        if attributes:
            params["attributes"] = ",".join(attributes)

        # Use the step answer endpoint for preview
        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.get(
                f"/users/current/steps/{step_id}/answer",
                params=params,
            ),
        )
