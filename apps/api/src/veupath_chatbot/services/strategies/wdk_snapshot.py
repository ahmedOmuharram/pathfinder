"""WDK strategy snapshot helpers (WDK payload → internal AST + persisted steps list)."""

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)

from .step_builders import build_steps_data_from_ast

logger = get_logger(__name__)


def _record_type_identifier(value: JSONValue) -> str | None:
    """Extract the record type identifier (e.g. 'transcript') from WDK payload values."""
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return None
        # Some payloads use the record class name; strip the suffix to get the URL segment.
        if v.endswith("RecordClass"):
            v = v[: -len("RecordClass")]
        return v or None
    if isinstance(value, dict):
        # Prefer stable identifier fields over display names.
        for key in ("urlSegment", "name", "id"):
            v_raw = value.get(key)
            if isinstance(v_raw, str):
                ident: str | None = _record_type_identifier(v_raw)
                if ident:
                    return ident
    return None


def _infer_record_type_from_wdk(
    wdk_strategy: JSONObject,
    steps: JSONObject | JSONArray,
    fallback: str,
) -> str:
    """Infer record type from WDK strategy + first step (prefer recordClassName)."""
    # 1) Strategy-level fields (most reliable when present)
    for key in (
        "recordClassName",
        "record_class_name",
        "recordType",
        "record_type",
        "recordTypeName",
        "recordTypeId",
    ):
        ident = _record_type_identifier(wdk_strategy.get(key))
        if ident:
            return ident

    # 2) Fall back to the first step's record fields
    first: JSONValue | None = None
    if isinstance(steps, dict) and steps:
        first = next(iter(steps.values()))
    elif isinstance(steps, list) and steps:
        first = steps[0]
    if isinstance(first, dict):
        for key in ("recordClassName", "recordType", "recordTypeId", "recordTypeName"):
            ident = _record_type_identifier(first.get(key))
            if ident:
                return ident

    return fallback


def _get_step_info(steps: JSONObject | JSONArray, step_id: int) -> JSONObject:
    if isinstance(steps, dict):
        step_str = str(step_id)
        result = steps.get(step_str)
        if isinstance(result, dict):
            return result
        # Try with int key if it's a dict that might have int keys
        # Note: JSONObject has str keys, but WDK sometimes uses int keys
        # We need to check both, but mypy will complain about int indexing
        # Convert int key to string for proper dict access
        step_id_str = str(step_id)
        if step_id_str in steps:
            result_raw = steps.get(step_id_str)
            if isinstance(result_raw, dict):
                return result_raw
        return {}
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                step_id_val = step.get("stepId") or step.get("id")
                if step_id_val == step_id or str(step_id_val) == str(step_id):
                    return step
    return {}


def _extract_operator(parameters: JSONObject) -> str | None:
    if not parameters:
        return None
    for key, value in parameters.items():
        if "operator" in str(key).lower():
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                return str(value[0])
    return None


def _extract_result_count(step_info: JSONObject) -> int | None:
    if not step_info:
        return None
    keys = ("estimatedSize", "estimated_size", "count", "resultCount", "result_count")
    for key in keys:
        value = step_info.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    for value in step_info.values():
        if isinstance(value, dict):
            nested = _extract_result_count(value)
            if nested is not None:
                return nested
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = _extract_result_count(item)
                    if nested is not None:
                        return nested
    return None


def _attach_counts_from_wdk_strategy(
    steps_data: JSONArray, wdk_strategy: JSONObject
) -> None:
    steps_info_raw = wdk_strategy.get("steps")
    steps_info: JSONObject = {}
    if isinstance(steps_info_raw, dict):
        steps_info = steps_info_raw
    elif isinstance(steps_info_raw, list):
        # Convert list to dict keyed by stepId
        for step_item in steps_info_raw:
            if isinstance(step_item, dict):
                step_id_val = step_item.get("stepId") or step_item.get("id")
                if step_id_val is not None:
                    steps_info[str(step_id_val)] = step_item
    if not steps_info:
        return
    for step_value in steps_data:
        if not isinstance(step_value, dict):
            continue
        step = as_json_object(step_value)
        step_id = step.get("wdkStepId") or step.get("id")
        if step_id is None:
            continue
        step_id_str = str(step_id)
        step_info_raw = steps_info.get(step_id_str)
        step_info: JSONObject = {}
        if isinstance(step_info_raw, dict):
            step_info = as_json_object(step_info_raw)
        if not step_info:
            continue
        count = _extract_result_count(step_info)
        if count is not None:
            step["resultCount"] = count


def _normalize_operator(raw: str | None) -> str:
    if not raw:
        return "INTERSECT"
    upper = raw.upper()
    mapping = {
        "AND": "INTERSECT",
        "OR": "UNION",
        "UNION": "UNION",
        "INTERSECT": "INTERSECT",
        "MINUS": "MINUS_LEFT",
        "MINUS_LEFT": "MINUS_LEFT",
        "MINUS_RIGHT": "MINUS_RIGHT",
        "NOT": "MINUS_LEFT",
    }
    return mapping.get(upper, "INTERSECT")


def _build_node_from_wdk(
    step_tree: JSONObject,
    steps: JSONObject | JSONArray,
    record_type: str,
) -> PlanStepNode:
    step_id_value = step_tree.get("stepId")
    if step_id_value is None:
        raise ValueError("Missing stepId in WDK stepTree node")
    step_id: int
    if isinstance(step_id_value, int):
        step_id = step_id_value
    elif isinstance(step_id_value, (str, float)):
        try:
            step_id = int(step_id_value)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Invalid stepId type: {type(step_id_value)}") from err
    else:
        raise ValueError(f"Invalid stepId type: {type(step_id_value)}")
    step_info = _get_step_info(steps, step_id)
    search_name_value = (
        step_info.get("searchName")
        or step_info.get("searchNameShort")
        or step_info.get("searchNameFull")
        or step_info.get("searchNameLong")
    )
    search_name = str(search_name_value) if isinstance(search_name_value, str) else None
    search_config_value = step_info.get("searchConfig")
    search_config = (
        as_json_object(search_config_value)
        if isinstance(search_config_value, dict)
        else {}
    )
    parameters_value = search_config.get("parameters")
    parameters = (
        as_json_object(parameters_value) if isinstance(parameters_value, dict) else {}
    )
    display_name_value = step_info.get("customName") or search_name
    display_name = (
        str(display_name_value) if isinstance(display_name_value, str) else None
    )

    primary_input_value = step_tree.get("primaryInput")
    secondary_input_value = step_tree.get("secondaryInput")
    if primary_input_value and secondary_input_value:
        if not isinstance(primary_input_value, dict) or not isinstance(
            secondary_input_value, dict
        ):
            raise ValueError("primaryInput and secondaryInput must be objects")
        left = _build_node_from_wdk(
            as_json_object(primary_input_value), steps, record_type
        )
        right = _build_node_from_wdk(
            as_json_object(secondary_input_value), steps, record_type
        )
        operator = _normalize_operator(_extract_operator(parameters))
        return PlanStepNode(
            search_name=search_name or "boolean_question",
            operator=parse_op(operator),
            primary_input=left,
            secondary_input=right,
            display_name=display_name,
            id=str(step_id),
        )
    if primary_input_value:
        if not isinstance(primary_input_value, dict):
            raise ValueError("primaryInput must be an object")
        input_node = _build_node_from_wdk(
            as_json_object(primary_input_value), steps, record_type
        )
        return PlanStepNode(
            search_name=search_name or "Transform",
            primary_input=input_node,
            parameters=parameters,
            display_name=display_name,
            id=str(step_id),
        )
    return PlanStepNode(
        search_name=search_name or "UnknownSearch",
        parameters=parameters,
        display_name=display_name,
        id=str(step_id),
    )


def _build_snapshot_from_wdk(
    wdk_strategy: JSONObject,
    record_type_fallback: str,
) -> tuple[StrategyAST, JSONArray]:
    step_tree_value = wdk_strategy.get("stepTree") or wdk_strategy.get("stepTreeNode")
    if not isinstance(step_tree_value, dict):
        raise ValueError("WDK strategy does not include stepTree")
    step_tree = as_json_object(step_tree_value)

    steps_value = wdk_strategy.get("steps")
    steps: JSONObject | JSONArray
    if isinstance(steps_value, dict):
        steps = as_json_object(steps_value)
    elif isinstance(steps_value, list):
        steps = steps_value
    else:
        steps = {}
    record_type = _infer_record_type_from_wdk(wdk_strategy, steps, record_type_fallback)

    root = _build_node_from_wdk(step_tree, steps, record_type)
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

    # Enrich with WDK-specific fields when possible
    for step_value in steps_data:
        if not isinstance(step_value, dict):
            continue
        step = as_json_object(step_value)
        raw_id = step.get("id")
        wdk_step_id: int | None = None
        if raw_id is not None:
            try:
                if isinstance(raw_id, (int, float, str)):
                    wdk_step_id = int(raw_id)
            except TypeError, ValueError:
                wdk_step_id = None
        step["wdkStepId"] = wdk_step_id

        if wdk_step_id is None:
            continue
        step_info = _get_step_info(steps, wdk_step_id)
        if isinstance(step_info, dict):
            result_count = _extract_result_count(step_info)
            if result_count is not None:
                step["resultCount"] = result_count

    return ast, steps_data


async def _normalize_synced_parameters(
    ast: StrategyAST,
    steps_data: JSONArray,
    api: StrategyAPI,
) -> None:
    from veupath_chatbot.platform.types import as_json_object

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
            except Exception as exc:
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
                except Exception as fallback_exc:
                    logger.warning(
                        "Failed to load search details during WDK sync",
                        record_type=record_type,
                        search_name=search_name,
                        error=str(fallback_exc),
                    )
                    spec_cache[cache_key] = {}
                    continue
            if isinstance(details, dict):
                search_data = details.get("searchData")
                if isinstance(search_data, dict):
                    details = search_data
            spec_cache[cache_key] = details if isinstance(details, dict) else {}

        specs = adapt_param_specs(spec_cache.get(cache_key) or {})
        if not specs:
            continue
        try:
            normalizer = ParameterNormalizer(specs)
            normalized = normalizer.normalize(step.parameters or {})
        except Exception as exc:
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
