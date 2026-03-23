"""WDK -> plan conversion: parse typed WDK strategy models into internal plan.

Pure conversion functions (no I/O except ``normalize_synced_parameters`` which
fetches param specs from WDK).

Public API:
- ``build_snapshot_from_wdk`` -- WDKStrategyDetails -> StrategyPlanPayload (with step_counts and wdk_step_ids)
- ``normalize_synced_parameters`` -- enrich plan nodes with normalized param values
"""

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs_from_search
from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    walk_step_tree,
)
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.errors import AppError, DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas.strategies import StrategyPlanPayload

logger = get_logger(__name__)


# -- Internal conversion helpers ------------------------------------------------


def _extract_operator(parameters: dict[str, str]) -> str | None:
    """Find the boolean operator in a combine step's parameter dict."""
    for key, value in parameters.items():
        if "operator" in key.lower():
            return value
    return None


def _build_node(
    tree_node: WDKStepTree,
    steps: dict[str, WDKStep],
    record_type: str,
) -> PlanStepNode:
    """Recursively build a ``PlanStepNode`` tree from typed WDK models."""
    step_id = tree_node.step_id
    step = steps.get(str(step_id))
    if step is None:
        msg = (
            f"Step {step_id} not found in WDK steps dict "
            f"(available keys: {list(steps.keys())[:20]})"
        )
        raise DataParsingError(msg)

    search_name = step.search_name
    parameters: JSONObject = dict(step.search_config.parameters)
    display_name = step.custom_name or step.display_name or None

    if tree_node.primary_input and tree_node.secondary_input:
        left = _build_node(tree_node.primary_input, steps, record_type)
        right = _build_node(tree_node.secondary_input, steps, record_type)
        raw_operator = _extract_operator(step.search_config.parameters)
        if raw_operator is None:
            msg = (
                f"Combine step {step_id} has no boolean operator in "
                f"searchConfig.parameters (keys: {list(parameters.keys())})"
            )
            raise DataParsingError(msg)
        return PlanStepNode(
            search_name=search_name,
            operator=parse_op(raw_operator),
            primary_input=left,
            secondary_input=right,
            display_name=display_name,
            id=str(step_id),
        )
    if tree_node.primary_input:
        input_node = _build_node(tree_node.primary_input, steps, record_type)
        return PlanStepNode(
            search_name=search_name,
            primary_input=input_node,
            parameters=parameters,
            display_name=display_name,
            id=str(step_id),
        )
    return PlanStepNode(
        search_name=search_name,
        parameters=parameters,
        display_name=display_name,
        id=str(step_id),
    )


def _extract_wdk_metadata(
    root: PlanStepNode,
    wdk_steps: dict[str, WDKStep],
) -> tuple[dict[str, int], dict[str, int]]:
    """Extract step_counts and wdk_step_ids from plan tree matched against WDK steps."""
    step_counts: dict[str, int] = {}
    wdk_step_ids: dict[str, int] = {}
    for step in walk_step_tree(root):
        if not step.id.isdigit():
            continue
        wdk_id = int(step.id)
        wdk_step_ids[step.id] = wdk_id
        wdk_step = wdk_steps.get(str(wdk_id))
        if wdk_step is not None and wdk_step.estimated_size is not None:
            step_counts[step.id] = wdk_step.estimated_size
    return step_counts, wdk_step_ids


# -- Public API -----------------------------------------------------------------


def build_snapshot_from_wdk(
    wdk_strategy: WDKStrategyDetails,
) -> StrategyPlanPayload:
    """Convert a typed WDK strategy into a StrategyPlanPayload with enrichment metadata.

    Step counts and WDK step ID mappings are stored directly on the payload's
    ``step_counts`` and ``wdk_step_ids`` fields.
    """
    record_type = wdk_strategy.record_class_name or ""
    if not record_type.strip():
        msg = "WDK strategy is missing a valid 'recordClassName'"
        raise DataParsingError(msg)
    record_type = record_type.strip()

    root = _build_node(wdk_strategy.step_tree, wdk_strategy.steps, record_type)

    step_counts, wdk_step_ids = _extract_wdk_metadata(root, wdk_strategy.steps)
    return StrategyPlanPayload(
        record_type=record_type,
        root=root,
        name=wdk_strategy.name or None,
        description=wdk_strategy.description or None,
        step_counts=step_counts or None,
        wdk_step_ids=wdk_step_ids or None,
    )


# -- Parameter normalization ----------------------------------------------------


async def _load_search_spec(
    api: StrategyAPI,
    record_type: str,
    search_name: str,
    context: JSONObject,
) -> WDKSearch | None:
    """Load and unwrap search details for parameter normalization.

    Tries the context-aware endpoint first; falls back to the plain endpoint.
    Returns ``None`` when both fail.
    """
    try:
        response = await api.client.get_search_details_with_params(
            record_type,
            search_name,
            context=context,
            expand_params=True,
        )
    except AppError as exc:
        logger.warning(
            "Failed to load search details with params during WDK sync",
            record_type=record_type,
            search_name=search_name,
            error=str(exc),
        )
        try:
            response = await api.client.get_search_details(
                record_type, search_name, expand_params=True
            )
        except AppError as fallback_exc:
            logger.warning(
                "Failed to load search details during WDK sync",
                record_type=record_type,
                search_name=search_name,
                error=str(fallback_exc),
            )
            return None
    return response.search_data


async def normalize_synced_parameters(
    payload: StrategyPlanPayload,
    api: StrategyAPI,
) -> None:
    """Normalize parameters from WDK response using param specs.

    Mutates plan step nodes in place with normalized parameter values.
    """
    spec_cache: dict[tuple[str, str], WDKSearch | None] = {}

    for step in walk_step_tree(payload.root):
        if step.infer_kind() == "combine":
            continue
        search_name = step.search_name
        record_type = payload.record_type

        if not search_name or not record_type:
            continue

        cache_key = (record_type, search_name)
        if cache_key not in spec_cache:
            spec_cache[cache_key] = await _load_search_spec(
                api, record_type, search_name, step.parameters or {}
            )

        cached_search = spec_cache.get(cache_key)
        specs = adapt_param_specs_from_search(cached_search) if cached_search else {}
        if not specs:
            continue
        try:
            normalizer = ParameterNormalizer(specs)
            normalized = normalizer.normalize(step.parameters or {})
        except AppError as exc:
            logger.warning(
                "Failed to normalize synced parameters",
                record_type=record_type,
                search_name=search_name,
                step_id=step.id,
                error=str(exc),
            )
            continue

        step.parameters = normalized
