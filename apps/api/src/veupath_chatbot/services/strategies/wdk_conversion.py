"""WDK → AST conversion: parse WDK strategy payloads into internal AST.

Pure conversion functions (no I/O except `_normalize_synced_parameters` which
fetches param specs from WDK).

Public API:
- ``build_snapshot_from_wdk`` — full WDK strategy → (AST, steps_data, step_counts)
- ``extract_wdk_is_saved`` — extract isSaved flag from WDK payload
- ``parse_wdk_strategy_id`` — extract int ID from WDK list-strategies item
- ``normalize_synced_parameters`` — enrich AST nodes with normalized param values
"""

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    adapt_param_specs,
    unwrap_search_data,
)
from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.errors import AppError, DataParsingError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    as_json_object,
)

from .step_builders import build_steps_data_from_ast

logger = get_logger(__name__)


# ── Public helpers ─────────────────────────────────────────────────────


def extract_wdk_is_saved(payload: JSONObject) -> bool:
    """Extract ``payload["isSaved"]`` with isinstance guard, defaults False."""
    raw = payload.get("isSaved") if isinstance(payload, dict) else None
    return bool(raw) if isinstance(raw, bool) else False


def parse_wdk_strategy_id(item: JSONObject) -> int | None:
    """Extract integer WDK strategy ID from a list-strategies item.

    WDK's ``StrategyFormatter`` emits ``strategyId`` (``JsonKeys.STRATEGY_ID``)
    as a Java long (always an int in JSON).
    """
    wdk_id = item.get("strategyId")
    if isinstance(wdk_id, int):
        return wdk_id
    return None


# ── Internal conversion helpers ────────────────────────────────────────


def extract_record_type(wdk_strategy: JSONObject) -> str:
    """Extract the record type (urlSegment) from a WDK strategy payload."""
    value = wdk_strategy.get("recordClassName")
    if isinstance(value, str) and value.strip():
        return value.strip()
    msg = (
        f"WDK strategy is missing a valid 'recordClassName' "
        f"(got {type(value).__name__}: {value!r})"
    )
    raise DataParsingError(msg)


def get_step_info(steps: JSONObject, step_id: int) -> JSONObject:
    """Look up a step object from the WDK ``steps`` dict."""
    result = steps.get(str(step_id))
    if isinstance(result, dict):
        return result
    msg = (
        f"Step {step_id} not found in WDK steps dict "
        f"(available keys: {list(steps.keys())[:20]})"
    )
    raise DataParsingError(msg)


def extract_operator(parameters: JSONObject) -> str | None:
    if not parameters:
        return None
    for key, value in parameters.items():
        if "operator" in str(key).lower():
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                return str(value[0])
    return None


def extract_estimated_size(step_info: JSONObject) -> int | None:
    """Extract the result count from a WDK step object."""
    value = step_info.get("estimatedSize")
    if isinstance(value, int):
        return value
    return None


def build_node_from_wdk(
    step_tree: JSONObject,
    steps: JSONObject,
    record_type: str,
) -> PlanStepNode:
    """Recursively build a ``PlanStepNode`` tree from WDK stepTree + steps."""
    step_id_value = step_tree.get("stepId")
    if not isinstance(step_id_value, int):
        msg = (
            f"Expected int 'stepId' in stepTree node, got "
            f"{type(step_id_value).__name__}: {step_id_value!r}"
        )
        raise DataParsingError(msg)
    step_id: int = step_id_value

    step_info = get_step_info(steps, step_id)

    search_name_value = step_info.get("searchName")
    if not isinstance(search_name_value, str) or not search_name_value:
        msg = (
            f"Step {step_id} is missing a valid 'searchName' "
            f"(got {type(search_name_value).__name__}: {search_name_value!r})"
        )
        raise DataParsingError(msg)
    search_name: str = search_name_value

    search_config_value = step_info.get("searchConfig")
    if not isinstance(search_config_value, dict):
        msg = f"Step {step_id} is missing 'searchConfig'"
        raise DataParsingError(msg)
    search_config = as_json_object(search_config_value)
    parameters_value = search_config.get("parameters")
    parameters: JSONObject = (
        as_json_object(parameters_value) if isinstance(parameters_value, dict) else {}
    )

    custom_name = step_info.get("customName")
    display_name_value = step_info.get("displayName")
    display_name: str | None = (
        str(custom_name)
        if isinstance(custom_name, str) and custom_name
        else str(display_name_value)
        if isinstance(display_name_value, str) and display_name_value
        else None
    )

    primary_input_value = step_tree.get("primaryInput")
    secondary_input_value = step_tree.get("secondaryInput")
    if primary_input_value and secondary_input_value:
        if not isinstance(primary_input_value, dict) or not isinstance(
            secondary_input_value, dict
        ):
            msg = "primaryInput and secondaryInput must be objects"
            raise DataParsingError(msg)
        left = build_node_from_wdk(
            as_json_object(primary_input_value), steps, record_type
        )
        right = build_node_from_wdk(
            as_json_object(secondary_input_value), steps, record_type
        )
        raw_operator = extract_operator(parameters)
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
    if primary_input_value:
        if not isinstance(primary_input_value, dict):
            msg = "primaryInput must be an object"
            raise DataParsingError(msg)
        input_node = build_node_from_wdk(
            as_json_object(primary_input_value), steps, record_type
        )
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


def build_snapshot_from_wdk(
    wdk_strategy: JSONObject,
) -> tuple[StrategyAST, JSONArray, JSONObject]:
    """Convert a WDK strategy payload into an internal AST, steps list, and step counts.

    The steps list is used only for parameter normalization enrichment ---
    steps are derived from plan at read time and not persisted.

    The step counts dict maps step IDs (strings) to their ``estimatedSize``
    values from the WDK response, enabling zero-cost count display for
    WDK-linked strategies.
    """
    step_tree_value = wdk_strategy.get("stepTree")
    if not isinstance(step_tree_value, dict):
        msg = "WDK strategy is missing 'stepTree'"
        raise DataParsingError(msg)
    step_tree = as_json_object(step_tree_value)

    steps_value = wdk_strategy.get("steps")
    if not isinstance(steps_value, dict):
        msg = f"WDK strategy is missing 'steps' dict (got {type(steps_value).__name__})"
        raise DataParsingError(msg)
    steps: JSONObject = as_json_object(steps_value)

    record_type = extract_record_type(wdk_strategy)

    root = build_node_from_wdk(step_tree, steps, record_type)
    name_value = wdk_strategy.get("name")
    name = str(name_value) if isinstance(name_value, str) else None
    description_value = wdk_strategy.get("description")
    description = str(description_value) if isinstance(description_value, str) else None
    ast = StrategyAST(
        record_type=record_type,
        root=root,
        name=name,
        description=description,
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
        step_info_raw = steps.get(str(wdk_step_id))
        if isinstance(step_info_raw, dict):
            count = extract_estimated_size(as_json_object(step_info_raw))
            if count is not None:
                step["resultCount"] = count
                step_counts[str(wdk_step_id)] = count

    return ast, steps_data, step_counts


async def normalize_synced_parameters(
    ast: StrategyAST,
    steps_data: JSONArray,
    api: StrategyAPI,
) -> None:
    """Normalize parameters from WDK response using param specs.

    Mutates AST nodes in place with normalized parameter values.
    """
    steps_by_id: dict[str, JSONObject] = {}
    for step_value in steps_data:
        if not isinstance(step_value, dict):
            continue
        step_data = as_json_object(step_value)
        step_id_value = step_data.get("id")
        if step_id_value is not None:
            steps_by_id[str(step_id_value)] = step_data
    spec_cache: dict[tuple[str, str], JSONObject] = {}

    for step in ast.get_all_steps():
        if step.infer_kind() == "combine":
            continue
        search_name = step.search_name
        record_type = ast.record_type

        if not search_name or not record_type:
            continue

        cache_key = (record_type, search_name)
        if cache_key not in spec_cache:
            try:
                details = await api.client.get_search_details_with_params(
                    record_type,
                    search_name,
                    context=step.parameters or {},
                    expand_params=True,
                )
            except (AppError, ValueError, TypeError) as exc:
                logger.warning(
                    "Failed to load search details with params during WDK sync",
                    record_type=record_type,
                    search_name=search_name,
                    error=str(exc),
                )
                try:
                    details = await api.client.get_search_details(
                        record_type, search_name, expand_params=True
                    )
                except (AppError, ValueError, TypeError) as fallback_exc:
                    logger.warning(
                        "Failed to load search details during WDK sync",
                        record_type=record_type,
                        search_name=search_name,
                        error=str(fallback_exc),
                    )
                    spec_cache[cache_key] = {}
                    continue
            details = unwrap_search_data(details) or {}
            spec_cache[cache_key] = details if isinstance(details, dict) else {}

        specs = adapt_param_specs(spec_cache.get(cache_key) or {})
        if not specs:
            continue
        try:
            normalizer = ParameterNormalizer(specs)
            normalized = normalizer.normalize(step.parameters or {})
        except (ValueError, TypeError, KeyError) as exc:
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
