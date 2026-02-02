"""VEuPathDB Strategy API - create steps and strategies.

This implements the WDK REST pattern:
1. Create unattached steps via POST /users/current/steps
2. Compose a tree via POST /users/current/strategies with stepTree
"""

from typing import Any

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient

logger = get_logger(__name__)


# Use current user session (guest or authenticated)
CURRENT_USER = "current"


class StepTreeNode:
    """Node in a step tree (for building strategy)."""

    def __init__(
        self,
        step_id: int,
        primary_input: "StepTreeNode | None" = None,
        secondary_input: "StepTreeNode | None" = None,
    ) -> None:
        self.step_id = step_id
        self.primary_input = primary_input
        self.secondary_input = secondary_input

    def to_dict(self) -> dict[str, Any]:
        """Convert to WDK stepTree format."""
        result: dict[str, Any] = {"stepId": self.step_id}
        if self.primary_input:
            result["primaryInput"] = self.primary_input.to_dict()
        if self.secondary_input:
            result["secondaryInput"] = self.secondary_input.to_dict()
        return result


class StrategyAPI:
    """API for creating and managing WDK strategies."""

    def __init__(self, client: VEuPathDBClient, user_id: str = CURRENT_USER) -> None:
        self.client = client
        self.user_id = user_id
        self._session_initialized = False
        self._boolean_search_cache: dict[str, str] = {}

    def _normalize_param_value(self, value: Any) -> str:
        """Normalize parameters to WDK-accepted string values."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, dict)):
            import json

            return json.dumps(value)
        return str(value)

    def _normalize_parameters(self, parameters: dict[str, Any]) -> dict[str, str]:
        return {
            key: self._normalize_param_value(value)
            for key, value in (parameters or {}).items()
        }

    async def _ensure_session(self) -> None:
        """Initialize session cookies for the current user."""
        if self._session_initialized:
            return
        await self.client.get("/users/current")
        self._session_initialized = True

    async def _get_boolean_search_name(self, record_type: str) -> str:
        """Resolve the boolean combine search name for a record type."""
        if record_type in self._boolean_search_cache:
            return self._boolean_search_cache[record_type]

        searches = await self.client.get_searches(record_type)
        for search in searches:
            name = search.get("urlSegment") or search.get("name") or ""
            if name.startswith("boolean_question"):
                self._boolean_search_cache[record_type] = name
                return name

        raise ValueError(
            f"No boolean combine search found for record type '{record_type}'"
        )

    async def _get_boolean_param_names(
        self, record_type: str
    ) -> tuple[str, str, str]:
        """Resolve parameter names for boolean combine search."""
        boolean_search = await self._get_boolean_search_name(record_type)
        details = await self.client.get_search_details(record_type, boolean_search)
        search_data = details.get("searchData", details)
        param_names = search_data.get("paramNames") or [
            p.get("name") for p in search_data.get("parameters", [])
        ]
        param_names = [p for p in param_names if p]

        left = next((p for p in param_names if p.startswith("bq_left_op")), None)
        right = next((p for p in param_names if p.startswith("bq_right_op")), None)
        op = next((p for p in param_names if p.startswith("bq_operator")), "bq_operator")

        if not left or not right:
            raise ValueError(
                f"Boolean param names not found for record type '{record_type}'"
            )

        return left, right, op

    async def create_step(
        self,
        record_type: str,
        search_name: str,
        parameters: dict[str, Any],
        custom_name: str | None = None,
    ) -> dict[str, Any]:
        """Create an unattached step.

        Args:
            record_type: Record type (e.g., "gene", "transcript")
            search_name: Name of the search question
            parameters: Search parameters
            custom_name: Optional custom name for the step

        Returns:
            Created step data with stepId
        """
        normalized_params = self._normalize_parameters(parameters)
        payload: dict[str, Any] = {
            "searchName": search_name,
            "searchConfig": {
                "parameters": normalized_params,
            },
        }
        if custom_name:
            payload["customName"] = custom_name

        logger.info(
            "Creating WDK step",
            record_type=record_type,
            search_name=search_name,
        )

        await self._ensure_session()
        return await self.client.post(
            f"/users/{self.user_id}/steps",
            json=payload,
        )

    async def create_combined_step(
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        custom_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a combined step (boolean operation).

        Args:
            primary_step_id: ID of the primary (left) step
            secondary_step_id: ID of the secondary (right) step
            boolean_operator: One of INTERSECT, UNION, MINUS, LMINUS, RMINUS
            custom_name: Optional custom name

        Returns:
            Created step data
        """
        await self._ensure_session()
        boolean_search = await self._get_boolean_search_name(record_type)
        left_param, right_param, op_param = await self._get_boolean_param_names(
            record_type
        )

        payload: dict[str, Any] = {
            "searchName": boolean_search,
            "searchConfig": {
                "parameters": {
                    # WDK requires empty inputs here; inputs are wired via stepTree
                    left_param: "",
                    right_param: "",
                    op_param: boolean_operator,
                },
            },
        }
        if custom_name:
            payload["customName"] = custom_name

        logger.info(
            "Creating combined step",
            primary=primary_step_id,
            secondary=secondary_step_id,
            operator=boolean_operator,
        )

        await self._ensure_session()
        return await self.client.post(
            f"/users/{self.user_id}/steps",
            json=payload,
        )

    async def create_transform_step(
        self,
        input_step_id: int,
        transform_name: str,
        parameters: dict[str, Any],
        custom_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a transform step.

        Args:
            input_step_id: ID of the input step
            transform_name: Name of the transform question
            parameters: Transform parameters
            custom_name: Optional custom name

        Returns:
            Created step data
        """
        normalized_params = self._normalize_parameters(parameters)
        payload: dict[str, Any] = {
            "searchName": transform_name,
            "searchConfig": {
                "parameters": normalized_params,
            },
        }
        if custom_name:
            payload["customName"] = custom_name

        logger.info(
            "Creating transform step",
            input=input_step_id,
            transform=transform_name,
        )
        logger.info(
            "Transform step payload",
            transform=transform_name,
            params=normalized_params,
        )

        await self._ensure_session()
        return await self.client.post(
            f"/users/{self.user_id}/steps",
            json=payload,
        )

    async def set_step_filter(
        self, step_id: int, filter_name: str, value: Any, disabled: bool = False
    ) -> Any:
        """Create or update a filter on a step."""
        await self._ensure_session()
        payload = {"name": filter_name, "value": value, "disabled": disabled}
        return await self.client.set_step_filter(
            self.user_id, step_id, filter_name, payload
        )

    async def delete_step_filter(self, step_id: int, filter_name: str) -> Any:
        """Remove a filter from a step."""
        await self._ensure_session()
        return await self.client.delete_step_filter(self.user_id, step_id, filter_name)

    async def list_analysis_types(self, step_id: int) -> list[dict[str, Any]]:
        """List available analysis types for a step."""
        await self._ensure_session()
        return await self.client.list_analysis_types(self.user_id, step_id)

    async def get_analysis_type(
        self, step_id: int, analysis_type: str
    ) -> dict[str, Any]:
        """Get analysis form metadata for a step."""
        await self._ensure_session()
        return await self.client.get_analysis_type(self.user_id, step_id, analysis_type)

    async def list_step_analyses(self, step_id: int) -> list[dict[str, Any]]:
        """List analyses that have been run on a step."""
        await self._ensure_session()
        return await self.client.list_step_analyses(self.user_id, step_id)

    async def list_step_filters(self, step_id: int) -> list[dict[str, Any]]:
        """List available filters for a step."""
        await self._ensure_session()
        return await self.client.list_step_filters(self.user_id, step_id)

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: dict[str, Any] | None = None,
        custom_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new analysis instance for a step."""
        await self._ensure_session()
        payload: dict[str, Any] = {
            "analysisType": analysis_type,
            "parameters": parameters or {},
        }
        if custom_name:
            payload["customName"] = custom_name
        return await self.client.create_step_analysis(self.user_id, step_id, payload)

    async def run_step_report(
        self, step_id: int, report_name: str, config: dict[str, Any] | None = None
    ) -> Any:
        """Run a report on a step."""
        await self._ensure_session()
        payload = {"reportConfig": config or {}}
        return await self.client.run_step_report(
            self.user_id, step_id, report_name, payload
        )

    async def create_strategy(
        self,
        step_tree: StepTreeNode,
        name: str,
        description: str | None = None,
        is_public: bool = False,
        is_saved: bool = True,
    ) -> dict[str, Any]:
        """Create a strategy from a step tree.

        Args:
            step_tree: Root of the step tree
            name: Strategy name
            description: Optional description

        Returns:
            Created strategy data
        """
        payload: dict[str, Any] = {
            "name": name,
            "isPublic": is_public,
            "isSaved": is_saved,
            "stepTree": step_tree.to_dict(),
        }
        if description:
            payload["description"] = description

        logger.info("Creating WDK strategy", name=name)

        await self._ensure_session()
        return await self.client.post(
            f"/users/{self.user_id}/strategies",
            json=payload,
        )

    async def get_strategy(self, strategy_id: int) -> dict[str, Any]:
        """Get a strategy by ID."""
        await self._ensure_session()
        return await self.client.get(
            f"/users/{self.user_id}/strategies/{strategy_id}"
        )

    async def list_strategies(self) -> list[dict[str, Any]]:
        """List strategies for the current user."""
        await self._ensure_session()
        return await self.client.get(
            f"/users/{self.user_id}/strategies"
        )

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: StepTreeNode | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Update a strategy."""
        payload: dict[str, Any] = {}
        if step_tree:
            payload["stepTree"] = step_tree.to_dict()
        if name:
            payload["name"] = name

        await self._ensure_session()
        return await self.client.patch(
            f"/users/{self.user_id}/strategies/{strategy_id}",
            json=payload,
        )

    async def delete_strategy(self, strategy_id: int) -> None:
        """Delete a strategy."""
        await self._ensure_session()
        await self.client.delete(
            f"/users/{self.user_id}/strategies/{strategy_id}"
        )

    async def get_step_answer(
        self,
        step_id: int,
        attributes: list[str] | None = None,
        pagination: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        """Get answer records for a step.

        Args:
            step_id: Step ID
            attributes: Attributes to include in response
            pagination: Offset and numRecords

        Returns:
            Answer data with records
        """
        params: dict[str, Any] = {}
        if attributes:
            params["attributes"] = ",".join(attributes)
        if pagination:
            params.update(pagination)

        await self._ensure_session()
        return await self.client.get(
            f"/users/{self.user_id}/steps/{step_id}/answer",
            params=params,
        )

    async def get_step_count(self, step_id: int) -> int:
        """Get result count for a step."""
        await self._ensure_session()
        answer = await self.client.post(
            f"/users/{self.user_id}/steps/{step_id}/reports/standard",
            json={
                "reportConfig": {"pagination": {"offset": 0, "numRecords": 0}},
            },
        )
        return (answer or {}).get("meta", {}).get("totalCount", 0)

