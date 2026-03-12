"""Step creation methods for the Strategy API.

Provides :class:`StepsMixin` with methods to create search steps,
combined (boolean) steps, transform steps, and datasets.
"""

from typing import cast

import httpx

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.integrations.veupathdb.param_utils import wdk_entity_name
from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.platform.errors import InternalError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class StepsMixin(StrategyAPIBase):
    """Mixin providing step creation and dataset upload methods."""

    async def _get_boolean_search_name(self, record_type: str) -> str:
        """Resolve the boolean combine search name for a record type."""
        if record_type in self._boolean_search_cache:
            return self._boolean_search_cache[record_type]

        searches = await self.client.get_searches(record_type)
        for search in searches:
            name = wdk_entity_name(search)
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
        search_data = unwrap_search_data(details) or details

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

    async def _get_answer_param_names(
        self,
        record_type: str,
        search_name: str,
    ) -> set[str]:
        """Return the set of ``input-step`` (AnswerParam) names for a search.

        Results are cached per ``record_type/search_name`` pair.

        :param record_type: WDK record type.
        :param search_name: Search/question URL segment.
        :returns: Set of parameter names whose type is ``input-step``.
        """
        cache_key = f"{record_type}/{search_name}"
        if cache_key in self._answer_param_cache:
            return self._answer_param_cache[cache_key]

        try:
            details = await self.client.get_search_details(record_type, search_name)
            search_data = unwrap_search_data(details)
            if not isinstance(search_data, dict):
                return set()
            params = search_data.get("parameters", [])
            if not isinstance(params, list):
                return set()
            names = {
                str(p["name"])
                for p in params
                if isinstance(p, dict) and p.get("type") == "input-step"
            }
            self._answer_param_cache[cache_key] = names
            return names
        except httpx.HTTPError, KeyError, TypeError:
            logger.warning(
                "Failed to fetch answer param names for %s/%s",
                record_type,
                search_name,
                exc_info=True,
            )
            return set()

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
        wdk_weight: int | None = None,
    ) -> JSONObject:
        """Create an unattached step.

        :param record_type: Record type (e.g., "gene", "transcript").
        :param search_name: Name of the search question.
        :param parameters: Search parameters.
        :param custom_name: Optional custom name for the step.
        :param wdk_weight: Optional WDK weight for result ranking in combined strategies.
        :returns: Created step data with stepId.
        """
        normalized_params = self._normalize_parameters(parameters)
        search_config: JSONObject = {
            "parameters": cast(JSONObject, normalized_params),
        }
        if wdk_weight is not None:
            search_config["wdkWeight"] = wdk_weight
        payload: JSONObject = {
            "searchName": search_name,
            "searchConfig": search_config,
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
        wdk_weight: int | None = None,
    ) -> JSONObject:
        """Create a combined step (boolean operation).

        :param primary_step_id: ID of the primary (left) step.
        :param secondary_step_id: ID of the secondary (right) step.
        :param boolean_operator: One of INTERSECT, UNION, MINUS, RMINUS, LONLY, RONLY.
        :param record_type: WDK record type.
        :param custom_name: Optional custom name.
        :param wdk_weight: Optional WDK weight for result ranking in combined strategies.
        :returns: Created step data.
        """
        await self._ensure_session()
        boolean_search = await self._get_boolean_search_name(record_type)
        left_param, right_param, op_param = await self._get_boolean_param_names(
            record_type
        )

        search_config: JSONObject = {
            "parameters": {
                # WDK requires empty inputs here; inputs are wired via stepTree
                left_param: "",
                right_param: "",
                op_param: boolean_operator,
            },
        }
        if wdk_weight is not None:
            search_config["wdkWeight"] = wdk_weight
        payload: JSONObject = {
            "searchName": boolean_search,
            "searchConfig": search_config,
        }
        if custom_name:
            payload["customName"] = custom_name

        logger.info(
            "Creating combined step",
            primary=primary_step_id,
            secondary=secondary_step_id,
            operator=boolean_operator,
        )

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
        record_type: str = "transcript",
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> JSONObject:
        """Create a transform step.

        WDK requires that ``input-step`` (AnswerParam) parameters are set to
        the empty string ``""`` when creating new steps — the actual input
        wiring happens via the ``stepTree`` at strategy creation time.

        This method fetches the search metadata to discover AnswerParam names,
        strips any stale values, and forces them to ``""``.

        :param input_step_id: ID of the input step (for logging; wiring
            happens in the strategy ``stepTree``).
        :param transform_name: Name of the transform question.
        :param parameters: Transform parameters.
        :param record_type: WDK record type for the search details lookup.
        :param custom_name: Optional custom name.
        :param wdk_weight: Optional WDK weight for result ranking in combined strategies.
        :returns: Created step data.
        """
        answer_param_names = await self._get_answer_param_names(
            record_type, transform_name
        )
        clean_params = dict(parameters or {})
        for ap_name in answer_param_names:
            clean_params[ap_name] = ""

        normalized_params = self._normalize_parameters(
            clean_params, keep_empty=answer_param_names
        )
        search_config: JSONObject = {
            "parameters": cast(JSONObject, normalized_params),
        }
        if wdk_weight is not None:
            search_config["wdkWeight"] = wdk_weight
        payload: JSONObject = {
            "searchName": transform_name,
            "searchConfig": search_config,
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
