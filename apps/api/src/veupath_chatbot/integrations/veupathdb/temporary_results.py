"""VEuPathDB /temporary-results helpers for downloads."""

from typing import Any

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient

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
        format_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a temporary result for download.

        Args:
            step_id: Step ID to export
            reporter: Reporter type (tabular, fullRecord, etc.)
            format_config: Reporter-specific configuration

        Returns:
            Temporary result info with ID and download URL
        """
        payload: dict[str, Any] = {
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
        return await self.client.post("/temporary-results", json=payload)

    async def get_temporary_result(self, result_id: str) -> dict[str, Any]:
        """Get status of a temporary result."""
        await self._ensure_session()
        return await self.client.get(f"/temporary-results/{result_id}")

    async def get_download_url(
        self,
        step_id: int,
        format: str = "csv",
        attributes: list[str] | None = None,
    ) -> str:
        """Get download URL for step results.

        Args:
            step_id: Step ID
            format: Output format (csv, tab, json)
            attributes: Attributes to include

        Returns:
            Download URL
        """
        format_config: dict[str, Any] = {}

        if format == "csv":
            format_config["type"] = "standard"
            format_config["includeHeader"] = True
            format_config["attachmentType"] = "text"
        elif format == "tab":
            format_config["type"] = "standard"
            format_config["includeHeader"] = True
            format_config["attachmentType"] = "text"
        elif format == "json":
            format_config["type"] = "json"

        if attributes:
            format_config["attributes"] = attributes

        result = await self.create_temporary_result(
            step_id=step_id,
            reporter="tabular" if format in ("csv", "tab") else "fullRecordJson",
            format_config=format_config,
        )

        return result.get("url", "")

    async def get_step_preview(
        self,
        step_id: int,
        limit: int = 100,
        attributes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get preview of step results.

        Args:
            step_id: Step ID
            limit: Max records to return
            attributes: Attributes to include

        Returns:
            Preview data with records
        """
        params: dict[str, Any] = {
            "numRecords": limit,
            "offset": 0,
        }
        if attributes:
            params["attributes"] = ",".join(attributes)

        # Use the step answer endpoint for preview
        await self._ensure_session()
        return await self.client.get(
            f"/users/current/steps/{step_id}/answer",
            params=params,
        )

