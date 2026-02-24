"""VEuPathDB Strategy API - create steps and strategies.

This implements the WDK REST pattern:
1. Create unattached steps via POST /users/current/steps
2. Compose a tree via POST /users/current/strategies with stepTree
"""

from typing import cast

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.platform.errors import InternalError
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
    """Check if a WDK strategy name is a Pathfinder internal helper strategy.

    Internal strategies are used for control tests and step counts.
    They are tagged with ``__pathfinder_internal__:`` prefix.

    :param name: WDK strategy name or None.
    :returns: True if the name indicates an internal strategy.
    """
    return bool(name) and str(name).startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX)


def _tag_internal_wdk_strategy_name(name: str) -> str:
    if name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX):
        return name
    return f"{PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX}{name}"


def strip_internal_wdk_strategy_name(name: str) -> str:
    """Remove the internal strategy name prefix if present.

    :param name: WDK strategy name (may include internal prefix).
    :returns: Display name without the ``__pathfinder_internal__:`` prefix.
    """
    if name.startswith(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX):
        return name[len(PATHFINDER_INTERNAL_STRATEGY_NAME_PREFIX) :]
    return name


# Use current user session (guest or authenticated)
CURRENT_USER = "current"


class StepTreeNode:
    """Node in a step tree (for building strategy).

    Represents a single step with optional primary (and for combines, secondary)
    input references. Used to build the ``stepTree`` payload for WDK strategy
    creation.
    """

    def __init__(
        self,
        step_id: int,
        primary_input: StepTreeNode | None = None,
        secondary_input: StepTreeNode | None = None,
    ) -> None:
        """Build a step tree node.

        :param step_id: WDK step ID (integer from create_step).
        :param primary_input: Child node for unary/binary operations.
        :param secondary_input: Second child for combine (e.g. UNION) steps.
        """
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
    """API for creating and managing WDK strategies.

    Provides methods to create steps, compose step trees, build strategies,
    run reports, and manage datasets. Follows the WDK REST pattern:
    create unattached steps, then POST a strategy with a stepTree linking them.
    """

    def __init__(self, client: VEuPathDBClient, user_id: str = CURRENT_USER) -> None:
        """Initialize the strategy API.

        :param client: VEuPathDB HTTP client (site-specific).
        :param user_id: WDK user ID; defaults to ``"current"`` (resolved at first use).
        """
        self.client = client
        self.user_id = user_id
        self._session_initialized = False
        self._boolean_search_cache: dict[str, str] = {}

    def _normalize_param_value(self, value: JSONValue) -> str:
        """Normalize parameters to WDK-accepted string values.

        :param value: Value to process.

        """
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
            # WDK UserFormatter emits the user ID under JsonKeys.ID = "id".
            candidate = me.get("id")
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
            # WDK uses JsonKeys.URL_SEGMENT = "urlSegment" for search names.
            name_raw = search.get("urlSegment")
            name = str(name_raw) if isinstance(name_raw, str) else ""
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
        # WDK wraps search details under JsonKeys.SEARCH_DATA = "searchData".
        search_data_raw = details.get("searchData")
        search_data: JSONObject = (
            search_data_raw if isinstance(search_data_raw, dict) else details
        )

        # WDK emits JsonKeys.PARAM_NAMES = "paramNames" — a list of param name strings.
        param_names_raw = search_data.get("paramNames")
        if not isinstance(param_names_raw, list):
            raise ValueError(
                f"Boolean search '{boolean_search}' has no 'paramNames' list"
            )
        param_names = [str(p) for p in param_names_raw if p is not None]

        left = next((p for p in param_names if p.startswith("bq_left_op")), None)
        right = next((p for p in param_names if p.startswith("bq_right_op")), None)
        op = next((p for p in param_names if p.startswith("bq_operator")), None)

        if not left or not right or not op:
            raise ValueError(
                f"Boolean param names not found for record type '{record_type}' "
                f"(left={left}, right={right}, op={op}, params={param_names})"
            )

        return left, right, op

    async def create_dataset(self, ids: list[str]) -> int:
        """Upload an ID list as a WDK dataset and return the dataset ID.

        WDK DatasetParam parameters (type ``input-dataset``) expect an integer
        dataset ID, not raw IDs.  This method creates a transient dataset via
        ``POST /users/{userId}/datasets`` and returns the integer ID that can
        be used as the parameter value.

        :param ids: List of record IDs (e.g. gene locus tags).
        :returns: Integer dataset ID.
        :raises InternalError: If dataset creation fails or no ID is returned.
        """
        await self._ensure_session()
        payload: JSONObject = cast(
            JSONObject,
            {"sourceType": "idList", "sourceContent": {"ids": ids}},
        )
        result = await self.client.post(
            f"/users/{self.user_id}/datasets",
            json=payload,
        )
        if isinstance(result, dict):
            ds_id = result.get("id")
            if isinstance(ds_id, int):
                logger.info(
                    "Created WDK dataset",
                    dataset_id=ds_id,
                    id_count=len(ids),
                )
                return ds_id
        raise InternalError(
            title="Dataset creation failed",
            detail=f"WDK returned unexpected response: {result!r}",
        )

    async def create_step(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        custom_name: str | None = None,
    ) -> JSONObject:
        """Create an unattached step.

        :param record_type: Record type (e.g., "gene", "transcript").
        :param search_name: Name of the search question.
        :param parameters: Search parameters.
        :param custom_name: Optional custom name for the step.
        :returns: Created step data with stepId.
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

        :param primary_step_id: ID of the primary (left) step.
        :param secondary_step_id: ID of the secondary (right) step.
        :param boolean_operator: One of INTERSECT, UNION, MINUS, LMINUS, RMINUS.
        :param record_type: WDK record type.
        :param custom_name: Optional custom name.
        :returns: Created step data.
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

        :param input_step_id: ID of the input step.
        :param transform_name: Name of the transform question.
        :param parameters: Transform parameters.
        :param custom_name: Optional custom name.
        :returns: Created step data.
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
            "analysisName": analysis_type,
            "parameters": parameters or {},
        }
        if custom_name:
            payload["displayName"] = custom_name
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
        is_saved: bool = False,
        is_internal: bool = False,
    ) -> JSONObject:
        """Create a strategy from a step tree.

        :param step_tree: Root of the step tree.
        :param name: Strategy name.
        :param description: Optional description.
        :param is_public: Whether the strategy is public.
        :param is_saved: Whether the strategy is saved.
        :param is_internal: Whether to tag as internal (Pathfinder helper).
        :returns: Created strategy data.
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

    async def set_saved(self, strategy_id: int, is_saved: bool) -> None:
        """Set the isSaved flag on a WDK strategy (draft vs saved)."""
        await self._ensure_session()
        await self.client.patch(
            f"/users/{self.user_id}/strategies/{strategy_id}",
            json={"isSaved": is_saved},
        )

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
        """Get answer records for a step via the standard report endpoint.

        :param step_id: Step ID.
        :param attributes: Attributes to include in response.
        :param pagination: Offset and numRecords.
        :returns: Answer data with records.
        """
        report_config: JSONObject = {}
        if attributes:
            report_config["attributes"] = cast(JSONValue, attributes)
        if pagination:
            report_config["pagination"] = cast(JSONValue, pagination)

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps/{step_id}/reports/standard",
                json={"reportConfig": report_config},
            ),
        )

    async def get_step_records(
        self,
        step_id: int,
        attributes: list[str] | None = None,
        tables: list[str] | None = None,
        pagination: dict[str, int] | None = None,
        sorting: list[JSONObject] | None = None,
    ) -> JSONObject:
        """Get paginated records for a step with configurable attributes and sorting.

        :param step_id: WDK step ID (must be part of a strategy).
        :param attributes: Attribute names to include.
        :param tables: Table names to include.
        :param pagination: ``{offset, numRecords}`` for server-side paging.
        :param sorting: List of ``{attributeName, direction}`` dicts.
        :returns: Standard report response with ``records`` and ``meta``.
        """
        report_config: JSONObject = {}
        if attributes:
            report_config["attributes"] = cast(JSONValue, attributes)
        if tables:
            report_config["tables"] = cast(JSONValue, tables)
        if pagination:
            report_config["pagination"] = cast(JSONValue, pagination)
        if sorting:
            report_config["sorting"] = cast(JSONValue, sorting)

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/users/{self.user_id}/steps/{step_id}/reports/standard",
                json={"reportConfig": report_config},
            ),
        )

    async def get_record_type_info(self, record_type: str) -> JSONObject:
        """Get expanded record type info including attributes and tables.

        :param record_type: WDK record type (e.g. "gene").
        :returns: Record type metadata with attribute fields.
        """
        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.get(
                f"/record-types/{record_type}",
                params={"format": "expanded"},
            ),
        )

    async def get_single_record(
        self,
        record_type: str,
        primary_key: list[JSONObject],
        attributes: list[str] | None = None,
        tables: list[str] | None = None,
    ) -> JSONObject:
        """Fetch a single record by its primary key.

        WDK's ``POST /record-types/{type}/records`` requires ``primaryKey``,
        ``attributes``, and ``tables`` arrays in the request body.  When
        ``attributes`` or ``tables`` are not provided we send empty arrays
        which tells WDK to return the default set.

        :param record_type: WDK record type.
        :param primary_key: List of ``{name, value}`` primary key parts.
        :param attributes: Attribute names to include (empty = default set).
        :param tables: Table names to include (empty = none).
        :returns: Full record with requested attributes/tables.
        """
        payload: JSONObject = {
            "primaryKey": cast(JSONValue, primary_key),
            "attributes": cast(JSONValue, attributes or []),
            "tables": cast(JSONValue, tables or []),
        }

        await self._ensure_session()
        return cast(
            JSONObject,
            await self.client.post(
                f"/record-types/{record_type}/records",
                json=payload,
            ),
        )

    async def get_filter_summary(self, step_id: int, filter_name: str) -> JSONObject:
        """Get filter summary distribution data for a step attribute.

        :param step_id: WDK step ID (must be part of a strategy).
        :param filter_name: Name of the filter to summarize.
        :returns: Filter summary JSON with distribution data.
        """
        await self._ensure_session()
        return await self.client.get_step_filter_summary(
            self.user_id, step_id, filter_name
        )

    async def get_step_count(self, step_id: int) -> int:
        """Get result count for a step.

        Uses the standard report endpoint and reads ``meta.totalCount``
        (``JsonKeys.TOTAL_COUNT``).
        """
        await self._ensure_session()
        answer = await self.client.post(
            f"/users/{self.user_id}/steps/{step_id}/reports/standard",
            json={
                "reportConfig": {"pagination": {"offset": 0, "numRecords": 0}},
            },
        )
        if not isinstance(answer, dict):
            raise ValueError(
                f"Step count: expected dict response, got {type(answer).__name__}"
            )
        meta_raw = answer.get("meta")
        if not isinstance(meta_raw, dict):
            raise ValueError("Step count: response missing 'meta' dict")
        total_count_raw = meta_raw.get("totalCount")
        if not isinstance(total_count_raw, int):
            raise ValueError(
                f"Step count: 'meta.totalCount' is not an int "
                f"(got {type(total_count_raw).__name__}: {total_count_raw!r})"
            )
        return total_count_raw
