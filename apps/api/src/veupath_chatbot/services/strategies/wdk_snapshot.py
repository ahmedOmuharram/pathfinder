"""WDK strategy snapshot helpers (WDK payload → internal AST + persisted steps list)."""

import asyncio
from typing import Any

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.strategy.ast import (
    CombineStep,
    SearchStep,
    StrategyAST,
    TransformStep,
)
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI

from .step_builders import build_steps_data_from_ast

logger = get_logger(__name__)

def _record_type_identifier(value: Any) -> str | None:
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
            v = value.get(key)
            if isinstance(v, str):
                ident = _record_type_identifier(v)
                if ident:
                    return ident
    return None


def _infer_record_type_from_wdk(
    wdk_strategy: dict[str, Any],
    steps: dict[str, Any] | list[dict[str, Any]],
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
    first: Any | None = None
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


def _get_step_info(
    steps: dict[str, Any] | list[dict[str, Any]], step_id: int
) -> dict[str, Any]:
    if isinstance(steps, dict):
        return steps.get(str(step_id)) or steps.get(step_id) or {}
    for step in steps:
        if step.get("stepId") == step_id or step.get("id") == step_id:
            return step
    return {}


def _extract_operator(parameters: dict[str, Any]) -> str | None:
    if not parameters:
        return None
    for key, value in parameters.items():
        if "operator" in str(key).lower():
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                return str(value[0])
    return None


def _extract_result_count(step_info: dict[str, Any]) -> int | None:
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


async def _attach_wdk_step_counts(steps_data: list[dict[str, Any]], api: StrategyAPI) -> None:
    async def fetch_count(step_id: int) -> int | None:
        try:
            return await api.get_step_count(step_id)
        except Exception:
            return None

    id_map: dict[int, dict[str, Any]] = {}
    for step in steps_data:
        raw_id = step.get("wdkStepId") or step.get("id")
        try:
            step_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        id_map[step_id] = step

    if not id_map:
        return

    tasks = [fetch_count(step_id) for step_id in id_map.keys()]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    for step_id, count in zip(id_map.keys(), results):
        if isinstance(count, int):
            id_map[step_id]["resultCount"] = count


def _attach_counts_from_wdk_strategy(
    steps_data: list[dict[str, Any]], wdk_strategy: dict[str, Any]
) -> None:
    steps_info = wdk_strategy.get("steps") or {}
    if not isinstance(steps_info, dict):
        return
    for step in steps_data:
        step_id = step.get("wdkStepId") or step.get("id")
        step_info = steps_info.get(str(step_id)) or steps_info.get(step_id)
        if not isinstance(step_info, dict):
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
    step_tree: dict[str, Any],
    steps: dict[str, Any] | list[dict[str, Any]],
    record_type: str,
) -> SearchStep | CombineStep | TransformStep:
    step_id = step_tree.get("stepId")
    if step_id is None:
        raise ValueError("Missing stepId in WDK stepTree node")
    step_info = _get_step_info(steps, step_id)
    search_name = (
        step_info.get("searchName")
        or step_info.get("searchNameShort")
        or step_info.get("searchNameFull")
        or step_info.get("searchNameLong")
    )
    search_config = step_info.get("searchConfig") or {}
    parameters = search_config.get("parameters") or {}
    display_name = step_info.get("customName") or search_name

    primary_input = step_tree.get("primaryInput")
    secondary_input = step_tree.get("secondaryInput")
    if primary_input and secondary_input:
        left = _build_node_from_wdk(primary_input, steps, record_type)
        right = _build_node_from_wdk(secondary_input, steps, record_type)
        operator = _normalize_operator(_extract_operator(parameters))
        return CombineStep(
            op=parse_op(operator),
            left=left,
            right=right,
            display_name=display_name,
            id=str(step_id),
        )
    if primary_input:
        input_node = _build_node_from_wdk(primary_input, steps, record_type)
        return TransformStep(
            transform_name=search_name or "Transform",
            input=input_node,
            parameters=parameters,
            display_name=display_name,
            id=str(step_id),
        )
    return SearchStep(
        record_type=record_type,
        search_name=search_name or "UnknownSearch",
        parameters=parameters,
        display_name=display_name,
        id=str(step_id),
    )


def _build_snapshot_from_wdk(
    wdk_strategy: dict[str, Any],
    record_type_fallback: str,
) -> tuple[StrategyAST, list[dict[str, Any]]]:
    step_tree = wdk_strategy.get("stepTree") or wdk_strategy.get("stepTreeNode")
    steps = wdk_strategy.get("steps") or {}
    record_type = _infer_record_type_from_wdk(wdk_strategy, steps, record_type_fallback)

    if not step_tree:
        raise ValueError("WDK strategy does not include stepTree")

    root = _build_node_from_wdk(step_tree, steps, record_type)
    ast = StrategyAST(
        record_type=record_type,
        root=root,
        name=wdk_strategy.get("name") or None,
        description=wdk_strategy.get("description"),
    )

    steps_data = build_steps_data_from_ast(ast, search_name_fallback_to_transform=True)

    # Enrich with WDK-specific fields when possible
    for step in steps_data:
        raw_id = step.get("id")
        try:
            wdk_step_id = int(raw_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
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
    steps_data: list[dict[str, Any]],
    api: StrategyAPI,
) -> None:
    steps_by_id = {str(step.get("id")): step for step in steps_data}
    spec_cache: dict[tuple[str, str], dict[str, Any]] = {}

    for step in ast.get_all_steps():
        if isinstance(step, CombineStep):
            continue
        if isinstance(step, SearchStep):
            search_name = step.search_name
            record_type = step.record_type
        else:
            search_name = step.transform_name
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
            if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
                details = details["searchData"]
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
        step_data = steps_by_id.get(str(step.id))
        if step_data is not None:
            step_data["parameters"] = normalized

