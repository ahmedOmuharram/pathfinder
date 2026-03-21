"""WDK → AST conversion: parse typed WDK strategy models into internal AST.

Pure conversion functions (no I/O except ``normalize_synced_parameters`` which
fetches param specs from WDK).

Public API:
- ``build_snapshot_from_wdk`` — WDKStrategyDetails → (AST, steps_data, step_counts)
- ``normalize_synced_parameters`` — enrich AST nodes with normalized param values
"""

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs_from_search
from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
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
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    as_json_object,
)

from .step_builders import build_steps_data_from_ast

logger = get_logger(__name__)


# ── Internal conversion helpers ────────────────────────────────────────


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


# ── Public API ─────────────────────────────────────────────────────────


def build_snapshot_from_wdk(
    wdk_strategy: WDKStrategyDetails,
) -> tuple[StrategyAST, JSONArray, JSONObject]:
    """Convert a typed WDK strategy into an internal AST, steps list, and step counts.

    The steps list is used only for parameter normalization enrichment ---
    steps are derived from plan at read time and not persisted.

    The step counts dict maps step IDs (strings) to their ``estimatedSize``
    values from the WDK response, enabling zero-cost count display for
    WDK-linked strategies.
    """
    record_type = wdk_strategy.record_class_name or ""
    if not record_type.strip():
        msg = "WDK strategy is missing a valid 'recordClassName'"
        raise DataParsingError(msg)
    record_type = record_type.strip()

    root = _build_node(wdk_strategy.step_tree, wdk_strategy.steps, record_type)
    ast = StrategyAST(
        record_type=record_type,
        root=root,
        name=wdk_strategy.name or None,
        description=wdk_strategy.description or None,
    )

    steps_data = build_steps_data_from_ast(ast)
    step_counts: JSONObject = {}

    for step_value in steps_data:
        if not isinstance(step_value, dict):
            continue
        step = as_json_object(step_value)
        raw_id = step.get("id")
        wdk_step_id: int | None = None
        if isinstance(raw_id, int):
            wdk_step_id = raw_id
        elif isinstance(raw_id, str) and raw_id.isdigit():
            wdk_step_id = int(raw_id)
        step["wdkStepId"] = wdk_step_id

        if wdk_step_id is None:
            continue
        wdk_step = wdk_strategy.steps.get(str(wdk_step_id))
        if wdk_step is not None and wdk_step.estimated_size is not None:
            step["resultCount"] = wdk_step.estimated_size
            step_counts[str(wdk_step_id)] = wdk_step.estimated_size

    return ast, steps_data, step_counts


# ── Parameter normalization ────────────────────────────────────────────


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


def _index_steps_by_id(steps_data: JSONArray) -> dict[str, JSONObject]:
    """Build a dict mapping step id → step data from a steps array."""
    steps_by_id: dict[str, JSONObject] = {}
    for step_value in steps_data:
        if not isinstance(step_value, dict):
            continue
        step_data = as_json_object(step_value)
        step_id_value = step_data.get("id")
        if step_id_value is not None:
            steps_by_id[str(step_id_value)] = step_data
    return steps_by_id


async def normalize_synced_parameters(
    ast: StrategyAST,
    steps_data: JSONArray,
    api: StrategyAPI,
) -> None:
    """Normalize parameters from WDK response using param specs.

    Mutates AST nodes in place with normalized parameter values.
    """
    steps_by_id = _index_steps_by_id(steps_data)
    spec_cache: dict[tuple[str, str], WDKSearch | None] = {}

    for step in ast.get_all_steps():
        if step.infer_kind() == "combine":
            continue
        search_name = step.search_name
        record_type = ast.record_type

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
        step_data_value = steps_by_id.get(str(step.id))
        if step_data_value is not None and isinstance(step_data_value, dict):
            step_data = as_json_object(step_data_value)
            step_data["parameters"] = normalized
