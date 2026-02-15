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
    as_json_object,
)

from .step_builders import build_steps_data_from_ast

logger = get_logger(__name__)


def _extract_record_type(wdk_strategy: JSONObject) -> str:
    """Extract the record type (urlSegment) from a WDK strategy payload.

    WDK's ``StrategyFormatter`` always emits ``recordClassName`` as the
    ``RecordClass::getUrlSegment()`` string (e.g. ``"gene"``, ``"transcript"``).

    Raises ``ValueError`` when the field is missing or not a non-empty string.

    :param wdk_strategy: WDK strategy payload.
    :returns: Record type urlSegment.
    :raises ValueError: If recordClassName is missing.
    """
    value = wdk_strategy.get("recordClassName")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(
        f"WDK strategy is missing a valid 'recordClassName' "
        f"(got {type(value).__name__}: {value!r})"
    )


def _get_step_info(steps: JSONObject, step_id: int) -> JSONObject:
    """Look up a step object from the WDK ``steps`` dict.

    WDK's ``StrategyFormatter.getDetailedStrategyJson`` always stores steps as
    a dict keyed by ``Long.toString(step.getStepId())``, so a simple string
    lookup is all that's needed.

    :param steps: WDK steps dict.
    :param step_id: Step ID.
    :returns: Step info dict.
    :raises ValueError: If step not found.
    """
    result = steps.get(str(step_id))
    if isinstance(result, dict):
        return result
    raise ValueError(
        f"Step {step_id} not found in WDK steps dict "
        f"(available keys: {list(steps.keys())[:20]})"
    )


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


def _extract_estimated_size(step_info: JSONObject) -> int | None:
    """Extract the result count from a WDK step object.

    WDK's ``StepFormatter`` emits ``estimatedSize`` as an ``Integer`` (may be
    ``null`` when the step hasn't been run yet).

    :param step_info: WDK step object.
    :returns: Estimated size or None.
    """
    value = step_info.get("estimatedSize")
    if isinstance(value, int):
        return value
    return None


def _attach_counts_from_wdk_strategy(
    steps_data: JSONArray, wdk_strategy: JSONObject
) -> None:
    """Enrich local ``steps_data`` with ``estimatedSize`` from the WDK payload.

    WDK's ``steps`` is always a dict keyed by string step-ID.

    :param steps_data: Local steps data to enrich.
    :param wdk_strategy: WDK strategy with steps dict.
    """
    steps_info_raw = wdk_strategy.get("steps")
    if not isinstance(steps_info_raw, dict) or not steps_info_raw:
        return
    steps_info: JSONObject = steps_info_raw

    for step_value in steps_data:
        if not isinstance(step_value, dict):
            continue
        step = as_json_object(step_value)
        wdk_step_id = step.get("wdkStepId")
        if wdk_step_id is None:
            continue
        step_info_raw = steps_info.get(str(wdk_step_id))
        if not isinstance(step_info_raw, dict):
            continue
        count = _extract_estimated_size(as_json_object(step_info_raw))
        if count is not None:
            step["resultCount"] = count


def _build_node_from_wdk(
    step_tree: JSONObject,
    steps: JSONObject,
    record_type: str,
) -> PlanStepNode:
    """Recursively build a ``PlanStepNode`` tree from WDK stepTree + steps.

    Field names used here correspond exactly to WDK's ``JsonKeys``:
    - ``stepTree`` nodes: ``stepId``, ``primaryInput``, ``secondaryInput``
    - ``steps`` dict entries: ``id``, ``searchName``, ``customName``,
      ``displayName``, ``searchConfig`` → ``parameters``

    :param step_tree: WDK stepTree node.
    :param steps: WDK steps dict.
    :param record_type: Record type urlSegment.
    :returns: PlanStepNode tree.
    """
    step_id_value = step_tree.get("stepId")
    if not isinstance(step_id_value, int):
        raise ValueError(
            f"Expected int 'stepId' in stepTree node, got "
            f"{type(step_id_value).__name__}: {step_id_value!r}"
        )
    step_id: int = step_id_value

    step_info = _get_step_info(steps, step_id)

    # WDK StepFormatter always emits "searchName" (JsonKeys.SEARCH_NAME).
    search_name_value = step_info.get("searchName")
    if not isinstance(search_name_value, str) or not search_name_value:
        raise ValueError(
            f"Step {step_id} is missing a valid 'searchName' "
            f"(got {type(search_name_value).__name__}: {search_name_value!r})"
        )
    search_name: str = search_name_value

    # searchConfig.parameters — always present on WDK steps.
    search_config_value = step_info.get("searchConfig")
    if not isinstance(search_config_value, dict):
        raise ValueError(f"Step {step_id} is missing 'searchConfig'")
    search_config = as_json_object(search_config_value)
    parameters_value = search_config.get("parameters")
    parameters: JSONObject = (
        as_json_object(parameters_value) if isinstance(parameters_value, dict) else {}
    )

    # Prefer user-set customName, fall back to auto-generated displayName.
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
            raise ValueError("primaryInput and secondaryInput must be objects")
        left = _build_node_from_wdk(
            as_json_object(primary_input_value), steps, record_type
        )
        right = _build_node_from_wdk(
            as_json_object(secondary_input_value), steps, record_type
        )
        raw_operator = _extract_operator(parameters)
        if raw_operator is None:
            raise ValueError(
                f"Combine step {step_id} has no boolean operator in "
                f"searchConfig.parameters (keys: {list(parameters.keys())})"
            )
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
            raise ValueError("primaryInput must be an object")
        input_node = _build_node_from_wdk(
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


def _build_snapshot_from_wdk(
    wdk_strategy: JSONObject,
) -> tuple[StrategyAST, JSONArray]:
    """Convert a WDK strategy payload into an internal AST and steps list.

    Expects the exact shape produced by WDK's ``StrategyFormatter.getDetailedStrategyJson``:
    - ``stepTree``: recursive tree of ``{stepId, primaryInput?, secondaryInput?}``
    - ``steps``: dict of ``stringStepId → stepObject``
    - ``recordClassName``: urlSegment string (e.g. ``"gene"``)

    :param wdk_strategy: WDK strategy payload from getDetailedStrategyJson.
    :returns: Tuple of (StrategyAST, steps list).
    :raises ValueError: If stepTree or steps is missing.
    """
    step_tree_value = wdk_strategy.get("stepTree")
    if not isinstance(step_tree_value, dict):
        raise ValueError("WDK strategy is missing 'stepTree'")
    step_tree = as_json_object(step_tree_value)

    steps_value = wdk_strategy.get("steps")
    if not isinstance(steps_value, dict):
        raise ValueError(
            f"WDK strategy is missing 'steps' dict (got {type(steps_value).__name__})"
        )
    steps: JSONObject = as_json_object(steps_value)

    record_type = _extract_record_type(wdk_strategy)

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

    # Enrich with WDK step IDs and result counts.
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
            count = _extract_estimated_size(as_json_object(step_info_raw))
            if count is not None:
                step["resultCount"] = count

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
