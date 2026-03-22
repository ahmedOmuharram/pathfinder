"""Step creation methods for the Strategy API.

Provides :class:`StepsMixin` with methods to create search steps,
combined (boolean) steps, and transform steps.
"""

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKIdentifier, WDKStep
from veupath_chatbot.platform.errors import AppError, DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class StepsMixin(StrategyAPIBase):
    """Mixin providing step creation methods."""

    async def _get_boolean_search_name(self, record_type: str) -> str:
        """Resolve the boolean combine search name for a record type."""
        if record_type in self._boolean_search_cache:
            return self._boolean_search_cache[record_type]

        searches = await self.client.get_searches(record_type)
        for search in searches:
            if search.url_segment.startswith("boolean_question"):
                self._boolean_search_cache[record_type] = search.url_segment
                return search.url_segment

        msg = f"No boolean combine search found for record type '{record_type}'"
        raise DataParsingError(msg)

    async def _get_boolean_param_names(self, record_type: str) -> tuple[str, str, str]:
        """Resolve parameter names for boolean combine search."""
        boolean_search = await self._get_boolean_search_name(record_type)
        response = await self.client.get_search_details(record_type, boolean_search)
        param_names = response.search_data.param_names

        left = next((p for p in param_names if p.startswith("bq_left_op")), None)
        right = next((p for p in param_names if p.startswith("bq_right_op")), None)
        op = next((p for p in param_names if p.startswith("bq_operator")), None)

        if not left or not right or not op:
            msg = (
                f"Boolean param names not found for record type '{record_type}' "
                f"(left={left}, right={right}, op={op}, params={param_names})"
            )
            raise DataParsingError(msg)

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
            response = await self.client.get_search_details(record_type, search_name)
            params = response.search_data.parameters or []
            names = {p.name for p in params if p.type == "input-step"}
        except AppError:
            logger.warning(
                "Failed to fetch answer param names for %s/%s",
                record_type,
                search_name,
                exc_info=True,
            )
            return set()
        self._answer_param_cache[cache_key] = names
        return names

    async def find_step(self, step_id: int, user_id: str | None = None) -> WDKStep:
        """Fetch a single step by ID. Matches monorepo's findStep."""
        uid = await self._get_user_id(user_id)
        raw = await self.client.get(f"/users/{uid}/steps/{step_id}")
        return WDKStep.model_validate(raw)

    async def create_step(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        custom_name: str | None = None,
        wdk_weight: int | None = None,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        """Create an unattached step.

        :param record_type: Record type (e.g., "gene", "transcript").
        :param search_name: Name of the search question.
        :param parameters: Search parameters.
        :param custom_name: Optional custom name for the step.
        :param wdk_weight: Optional WDK weight for result ranking in combined strategies.
        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        :returns: Created step identifier.
        """
        normalized_params = self._normalize_parameters(parameters)

        # Expand group codes in profile_pattern for GenesByOrthologPattern.
        if (
            search_name == "GenesByOrthologPattern"
            and "profile_pattern" in normalized_params
        ):
            normalized_params[
                "profile_pattern"
            ] = await self._expand_profile_pattern_groups(
                record_type,
                normalized_params["profile_pattern"],
            )

        # Expand parent tree nodes to leaves for multi-pick-vocabulary params
        # with countOnlyLeaves=true (e.g., organism).  WDK silently returns 0
        # genes for parent nodes — the frontend's CheckboxTree auto-selects
        # leaf descendants, and we must replicate that behaviour.
        normalized_params = await self._expand_tree_params_to_leaves(
            record_type,
            search_name,
            normalized_params,
        )

        step_params: JSONObject = {**normalized_params}
        search_config: JSONObject = {"parameters": step_params}
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

        uid = await self._get_user_id(user_id)
        raw = await self.client.post(
            f"/users/{uid}/steps",
            json=payload,
        )
        return WDKIdentifier.model_validate(raw)

    async def create_combined_step(  # noqa: PLR0913
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        custom_name: str | None = None,
        wdk_weight: int | None = None,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        """Create a combined step (boolean operation).

        :param primary_step_id: ID of the primary (left) step.
        :param secondary_step_id: ID of the secondary (right) step.
        :param boolean_operator: One of INTERSECT, UNION, MINUS, RMINUS, LONLY, RONLY.
        :param record_type: WDK record type.
        :param custom_name: Optional custom name.
        :param wdk_weight: Optional WDK weight for result ranking in combined strategies.
        :returns: Created step identifier.
        """
        uid = await self._get_user_id(user_id)
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

        raw = await self.client.post(
            f"/users/{uid}/steps",
            json=payload,
        )
        return WDKIdentifier.model_validate(raw)

    async def create_transform_step(  # noqa: PLR0913
        self,
        input_step_id: int,
        transform_name: str,
        parameters: JSONObject,
        record_type: str = "transcript",
        custom_name: str | None = None,
        wdk_weight: int | None = None,
        user_id: str | None = None,
    ) -> WDKIdentifier:
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
        :returns: Created step identifier.
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
        transform_params: JSONObject = {**normalized_params}
        search_config: JSONObject = {"parameters": transform_params}
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

        uid = await self._get_user_id(user_id)
        raw = await self.client.post(
            f"/users/{uid}/steps",
            json=payload,
        )
        return WDKIdentifier.model_validate(raw)
