"""VEuPathDB Strategy API - create steps and strategies.

This implements the WDK REST pattern:
1. Create unattached steps via POST /users/current/steps
2. Compose a tree via POST /users/current/strategies with stepTree
"""

from typing import cast

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

logger = get_logger(__name__)

# Internal (Pathfinder-created) WDK strategies.
#
# WDK doesn't support arbitrary metadata on a strategy. To reliably identify
# "internal helper" strategies (step counts, etc.) later, we tag the WDK name
# with a reserved prefix. This avoids incorrectly treating *all* unsaved
# strategies (`isSaved=false`) as internal.
PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX = "__pathfinder_internal__:"


def is_internal_wdk_strategy_name(name: str | None) -> bool:
    return bool(name) and str(name).startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)


def _tag_internal_wdk_strategy_name(name: str) -> str:
    if name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX):
        return name
    return f"{PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX}{name}"


def strip_internal_wdk_strategy_name(name: str) -> str:
    if name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX):
        return name[len(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX) :]
    return name


# Use current user session (guest or authenticated)
CURRENT_USER = "current"


class StepTreeNode:
    """Node in a step tree (for building strategy)."""

    def __init__(
        self,
        step_id: int,
        primary_input: StepTreeNode | None = None,
        secondary_input: StepTreeNode | None = None,
    ) -> None:
        self.step_id = step_id
        self.primary_input = primary_input
        self.secondary_input = secondary_input

    def to_dict(self) -> JSONObject:
        """Convert to WDK stepTree format."""
        result: JSONObject = {"stepId": self.step_id}
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

    def _normalize_param_value(self, value: JSONValue) -> str:
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

    def _normalize_parameters(self, parameters: JSONObject) -> dict[str, str]:
        return {
            key: self._normalize_param_value(value)
            for key, value in (parameters or {}).items()
        }

    async def _ensure_session(self) -> None:
        """Initialize session and resolve user id for mutation endpoints.

        Some WDK deployments allow GET/POST using `/users/current/...` but do NOT
        allow PUT/PATCH/DELETE on `/users/current/...` (405 Method Not Allowed).
        Resolve the concrete user id once and then use `/users/{userId}/...`.
        """
        if self._session_initialized:
            return
        me = await self.client.get("/users/current")
        resolved_user_id: str | None = None
        if isinstance(me, dict):
            # Different deployments vary in the key name.
            candidate = (
                me.get("userId")
                or me.get("userID")
                or me.get("id")
                or me.get("user_id")
            )
            if candidate is not None:
                resolved_user_id = str(candidate)

        # Only override when we were using the placeholder "current".
        if self.user_id == CURRENT_USER and resolved_user_id:
            logger.info(
                "Resolved WDK user id for mutations",
                resolved_user_id=resolved_user_id,
            )
            self.user_id = resolved_user_id
        self._session_initialized = True

    async def _get_boolean_search_name(self, record_type: str) -> str:
        """Resolve the boolean combine search name for a record type."""
        if record_type in self._boolean_search_cache:
            return self._boolean_search_cache[record_type]

        searches = await self.client.get_searches(record_type)
        for search_raw in searches:
            if not isinstance(search_raw, dict):
                continue
            search: JSONObject = search_raw
            name_raw = search.get("urlSegment") or search.get("name") or ""
            name = str(name_raw) if name_raw is not None else ""
            if name.startswith("boolean_question"):
                self._boolean_search_cache[record_type] = name
                return name

        raise ValueError(
            f"No boolean combine search found for record type '{record_type}'"
        )

    async def _get_boolean_param_names(self, record_type: str) -> tuple[str, str, str]:
        """Resolve parameter names for boolean combine search."""
        boolean_search = await self._get_boolean_search_name(record_type)
        details = await self.client.get_search_details(record_type, boolean_search)
        search_data_raw = details.get("searchData", details)
        if not isinstance(search_data_raw, dict):
            search_data: JSONObject = details
        else:
            search_data = search_data_raw

        param_names_raw = search_data.get("paramNames")
        if isinstance(param_names_raw, list):
            param_names = [str(p) for p in param_names_raw if p is not None]
        else:
            parameters_raw = search_data.get("parameters")
            param_names = []
            if isinstance(parameters_raw, list):
                for p in parameters_raw:
                    if isinstance(p, dict):
                        name_raw = p.get("name")
                        if name_raw is not None:
                            param_names.append(str(name_raw))

        left = next((p for p in param_names if p.startswith("bq_left_op")), None)
        right = next((p for p in param_names if p.startswith("bq_right_op")), None)
        op = next(
            (p for p in param_names if p.startswith("bq_operator")), "bq_operator"
        )

        if not left or not right:
            raise ValueError(
                f"Boolean param names not found for record type '{record_type}'"
            )

        return left, right, op

    async def create_step(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        custom_name: str | None = None,
    ) -> JSONObject:
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
        payload: JSONObject = {
            "searchName": search_name,
            "searchConfig": {
                "parameters": cast(JSONObject, normalized_params),
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
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps",
                json=payload,
            ),
        )

    async def create_combined_step(
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        custom_name: str | None = None,
    ) -> JSONObject:
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

        payload: JSONObject = {
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
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps",
                json=payload,
            ),
        )

    async def create_transform_step(
        self,
        input_step_id: int,
        transform_name: str,
        parameters: JSONObject,
        custom_name: str | None = None,
    ) -> JSONObject:
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
        payload: JSONObject = {
            "searchName": transform_name,
            "searchConfig": {
                "parameters": cast(JSONObject, normalized_params),
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
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps",
                json=payload,
            ),
        )

    async def set_step_filter(
        self, step_id: int, filter_name: str, value: JSONValue, disabled: bool = False
    ) -> JSONValue:
        """Create or update a filter on a step."""
        await self._ensure_session()
        payload = {"name": filter_name, "value": value, "disabled": disabled}
        return await self.client.set_step_filter(
            self.user_id, step_id, filter_name, payload
        )

    async def delete_step_filter(self, step_id: int, filter_name: str) -> JSONValue:
        """Remove a filter from a step."""
        await self._ensure_session()
        return await self.client.delete_step_filter(self.user_id, step_id, filter_name)

    async def list_analysis_types(self, step_id: int) -> JSONArray:
        """List available analysis types for a step."""
        await self._ensure_session()
        return await self.client.list_analysis_types(self.user_id, step_id)

    async def get_analysis_type(self, step_id: int, analysis_type: str) -> JSONObject:
        """Get analysis form metadata for a step."""
        await self._ensure_session()
        return await self.client.get_analysis_type(self.user_id, step_id, analysis_type)

    async def list_step_analyses(self, step_id: int) -> JSONArray:
        """List analyses that have been run on a step."""
        await self._ensure_session()
        return await self.client.list_step_analyses(self.user_id, step_id)

    async def list_step_filters(self, step_id: int) -> JSONArray:
        """List available filters for a step."""
        await self._ensure_session()
        return await self.client.list_step_filters(self.user_id, step_id)

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject:
        """Create a new analysis instance for a step."""
        await self._ensure_session()
        payload: JSONObject = {
            "analysisType": analysis_type,
            "parameters": parameters or {},
        }
        if custom_name:
            payload["customName"] = custom_name
        return await self.client.create_step_analysis(self.user_id, step_id, payload)

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> JSONValue:
        """Run a report on a step."""
        await self._ensure_session()
        # reportConfig is a nested JSONObject, which is valid JSONValue
        report_config: JSONValue = config or {}
        payload: JSONObject = {"reportConfig": report_config}
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
        is_internal: bool = False,
    ) -> JSONObject:
        """Create a strategy from a step tree.

        Args:
            step_tree: Root of the step tree
            name: Strategy name
            description: Optional description

        Returns:
            Created strategy data
        """
        if is_internal:
            name = _tag_internal_wdk_strategy_name(name)
            is_public = False
            is_saved = False

        payload: JSONObject = {
            "name": name,
            "isPublic": is_public,
            "isSaved": is_saved,
            "stepTree": step_tree.to_dict(),
        }
        if description:
            payload["description"] = description

        logger.info("Creating WDK strategy", name=name)

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/strategies",
                json=payload,
            ),
        )

    async def get_strategy(self, strategy_id: int) -> JSONObject:
        """Get a strategy by ID."""
        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.get(f"/users/{self.user_id}/strategies/{strategy_id}"),
        )

    async def list_strategies(self) -> JSONArray:
        """List strategies for the current user."""
        await self._ensure_session()
        return cast(
            JSONArray,
            await self.client.get(f"/users/{self.user_id}/strategies"),
        )

    async def update_strategy(
        self,
        strategy_id: int,
        step_tree: StepTreeNode | None = None,
        name: str | None = None,
    ) -> JSONObject:
        """Update a strategy."""
        await self._ensure_session()

        if step_tree is not None:
            await self.client.put(
                f"/users/{self.user_id}/strategies/{strategy_id}/step-tree",
                json={"stepTree": step_tree.to_dict()},
            )

        if name:
            await self.client.patch(
                f"/users/{self.user_id}/strategies/{strategy_id}",
                json={"name": name},
            )

        # Return the updated strategy payload (best-effort).
        return await self.get_strategy(strategy_id)

    async def delete_strategy(self, strategy_id: int) -> None:
        """Delete a strategy."""
        await self._ensure_session()
        await self.client.delete(f"/users/{self.user_id}/strategies/{strategy_id}")

    async def get_step_answer(
        self,
        step_id: int,
        attributes: list[str] | None = None,
        pagination: dict[str, int] | None = None,
    ) -> JSONObject:
        """Get answer records for a step.

        Args:
            step_id: Step ID
            attributes: Attributes to include in response
            pagination: Offset and numRecords

        Returns:
            Answer data with records
        """
        params: JSONObject = {}
        if attributes:
            params["attributes"] = ",".join(attributes)
        if pagination:
            params.update(pagination)

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.get(
                f"/users/{self.user_id}/steps/{step_id}/answer",
                params=params,
            ),
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
        if not isinstance(answer, dict):
            return 0
        answer_dict: JSONObject = answer
        meta_raw = answer_dict.get("meta")
        if not isinstance(meta_raw, dict):
            return 0
        meta: JSONObject = meta_raw
        total_count_raw = meta.get("totalCount")
        if isinstance(total_count_raw, int):
            return total_count_raw
        return 0
