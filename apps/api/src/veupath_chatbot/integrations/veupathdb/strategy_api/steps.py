"""Step creation and update methods for the Strategy API.

Provides :class:`StepsMixin` with methods to create search steps,
combined (boolean) steps, transform steps, and update existing steps.
"""

from veupath_chatbot.integrations.veupathdb.strategy_api.base import StrategyAPIBase
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    PatchStepSpec,
    WDKIdentifier,
    WDKSearchConfig,
    WDKStep,
)
from veupath_chatbot.platform.errors import AppError, DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


class StepsMixin(StrategyAPIBase):
    """Mixin providing step creation and update methods."""

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

    async def _prepare_search_config(
        self,
        raw_params: JSONObject,
        record_type: str,
        search_name: str,
        *,
        wdk_weight: int = 0,
        keep_empty: set[str] | None = None,
    ) -> tuple[dict[str, str], WDKSearchConfig]:
        """Normalize and expand parameters, return (normalized_params, search_config).

        Shared by create_step, create_transform_step, and update_step_search_config.
        Returns the normalized params dict AND a typed WDKSearchConfig.

        :param raw_params: Raw parameter dict (values may be non-string).
        :param record_type: WDK record type (e.g., "gene", "transcript").
        :param search_name: Search/question URL segment.
        :param wdk_weight: WDK weight for result ranking (0 = omit from payload).
        :param keep_empty: Param names to preserve even when empty (e.g. AnswerParams).
        :returns: Tuple of (normalized_params, search_config).
        """
        normalized = self._normalize_parameters(raw_params, keep_empty=keep_empty)

        # Expand group codes in profile_pattern for GenesByOrthologPattern.
        if search_name == "GenesByOrthologPattern" and "profile_pattern" in normalized:
            normalized["profile_pattern"] = await self._expand_profile_pattern_groups(
                record_type,
                normalized["profile_pattern"],
            )

        # Expand parent tree nodes to leaves for multi-pick-vocabulary params
        # with countOnlyLeaves=true (e.g., organism).  WDK silently returns 0
        # genes for parent nodes — the frontend's CheckboxTree auto-selects
        # leaf descendants, and we must replicate that behaviour.
        normalized = await self._expand_tree_params_to_leaves(
            record_type, search_name, normalized
        )

        search_config = WDKSearchConfig(parameters=normalized, wdk_weight=wdk_weight)
        return normalized, search_config

    async def create_step(
        self,
        spec: NewStepSpec,
        record_type: str,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        """Create an unattached step.

        :param spec: Step specification (search name, config, optional display fields).
        :param record_type: Record type (e.g., "gene", "transcript").
        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        :returns: Created step identifier.
        """
        _, search_config = await self._prepare_search_config(
            raw_params=dict(spec.search_config.parameters),
            record_type=record_type,
            search_name=spec.search_name,
            wdk_weight=spec.search_config.wdk_weight,
        )

        payload: JSONObject = {
            "searchName": spec.search_name,
            "searchConfig": search_config.model_dump(
                by_alias=True, exclude_defaults=True
            ),
        }
        if spec.custom_name:
            payload["customName"] = spec.custom_name

        logger.info(
            "Creating WDK step",
            record_type=record_type,
            search_name=spec.search_name,
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
        *,
        spec_overrides: PatchStepSpec | None = None,
        wdk_weight: int | None = None,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        """Create a combined step (boolean operation).

        :param primary_step_id: ID of the primary (left) step.
        :param secondary_step_id: ID of the secondary (right) step.
        :param boolean_operator: One of INTERSECT, UNION, MINUS, RMINUS, LONLY, RONLY.
        :param record_type: WDK record type.
        :param spec_overrides: Optional display overrides (custom name, etc.).
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
        if spec_overrides and spec_overrides.custom_name:
            payload["customName"] = spec_overrides.custom_name

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

    async def create_transform_step(
        self,
        spec: NewStepSpec,
        input_step_id: int,
        record_type: str = "transcript",
        *,
        user_id: str | None = None,
    ) -> WDKIdentifier:
        """Create a transform step.

        WDK requires that ``input-step`` (AnswerParam) parameters are set to
        the empty string ``""`` when creating new steps — the actual input
        wiring happens via the ``stepTree`` at strategy creation time.

        This method fetches the search metadata to discover AnswerParam names,
        strips any stale values, and forces them to ``""``.

        :param spec: Step specification (search name, config, optional display fields).
        :param input_step_id: ID of the input step (for logging; wiring
            happens in the strategy ``stepTree``).
        :param record_type: WDK record type for the search details lookup.
        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        :returns: Created step identifier.
        """
        answer_param_names = await self._get_answer_param_names(
            record_type, spec.search_name
        )
        clean_params: JSONObject = dict(spec.search_config.parameters)
        for ap_name in answer_param_names:
            clean_params[ap_name] = ""

        normalized, search_config = await self._prepare_search_config(
            raw_params=clean_params,
            record_type=record_type,
            search_name=spec.search_name,
            wdk_weight=spec.search_config.wdk_weight,
            keep_empty=answer_param_names,
        )

        payload: JSONObject = {
            "searchName": spec.search_name,
            "searchConfig": search_config.model_dump(
                by_alias=True, exclude_defaults=True
            ),
        }
        if spec.custom_name:
            payload["customName"] = spec.custom_name

        logger.info(
            "Creating transform step",
            input=input_step_id,
            transform=spec.search_name,
        )
        logger.info(
            "Transform step payload",
            transform=spec.search_name,
            params=normalized,
        )

        uid = await self._get_user_id(user_id)
        raw = await self.client.post(
            f"/users/{uid}/steps",
            json=payload,
        )
        return WDKIdentifier.model_validate(raw)

    async def update_step_search_config(
        self,
        step_id: int,
        search_config: WDKSearchConfig,
        record_type: str,
        search_name: str,
        *,
        user_id: str | None = None,
    ) -> None:
        """Update a step's search configuration (parameters + weight).

        Matches monorepo's ``StepsService.updateStepSearchConfig``.
        Endpoint: ``PUT /users/{uid}/steps/{step_id}/search-config``

        Parameters are normalized and expanded (profile pattern groups,
        tree param leaves) identically to step creation.

        :param step_id: WDK step ID to update.
        :param search_config: New search configuration.
        :param record_type: WDK record type (needed for param expansion).
        :param search_name: Search URL segment (needed for param expansion).
        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        """
        _, config_payload = await self._prepare_search_config(
            raw_params=dict(search_config.parameters),
            record_type=record_type,
            search_name=search_name,
            wdk_weight=search_config.wdk_weight,
        )

        logger.info(
            "Updating step search config",
            step_id=step_id,
            search_name=search_name,
        )

        uid = await self._get_user_id(user_id)
        await self.client.put(
            f"/users/{uid}/steps/{step_id}/search-config",
            json=config_payload.model_dump(by_alias=True, exclude_defaults=True),
        )

    async def update_step_properties(
        self,
        step_id: int,
        spec: PatchStepSpec,
        *,
        user_id: str | None = None,
    ) -> None:
        """Update a step's display properties (name, expanded state, preferences).

        Matches monorepo's ``StepsService.updateStepProperties``.
        Endpoint: ``PATCH /users/{uid}/steps/{step_id}``

        :param step_id: WDK step ID to update.
        :param spec: Patch specification with fields to update (None fields excluded).
        :param user_id: Explicit user ID override, or ``None`` to use resolved.
        """
        payload = spec.model_dump(by_alias=True, exclude_none=True, mode="json")

        logger.info(
            "Updating step properties",
            step_id=step_id,
            fields=list(payload.keys()),
        )

        uid = await self._get_user_id(user_id)
        await self.client.patch(
            f"/users/{uid}/steps/{step_id}",
            json=payload,
        )
