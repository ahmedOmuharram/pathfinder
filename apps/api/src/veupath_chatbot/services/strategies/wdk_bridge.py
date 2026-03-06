"""WDK Bridge: all VEuPathDB WDK <-> internal conversion in one place.

Consolidates wdk_snapshot.py, wdk_sync.py, and wdk_counts.py into a single
module with a clean public API:

- ``fetch_and_convert`` — fetch WDK strategy, convert to AST, normalize params
- ``sync_to_projection`` — full sync flow: fetch + upsert into CQRS
- ``upsert_projection`` — create-or-update a stream projection from WDK data
- ``compute_step_counts`` — compile plan in WDK and read estimatedSize values
- ``parse_wdk_strategy_id`` — extract int ID from WDK list-strategies item
- ``extract_wdk_is_saved`` — extract isSaved flag from WDK payload
- ``wdk_error_boundary`` — async context manager for consistent WDK error handling
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs
from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.compile import compile_strategy
from veupath_chatbot.domain.strategy.ops import parse_op
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.platform.errors import AppError, WDKError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    as_json_object,
)
from veupath_chatbot.services.control_helpers import delete_temp_strategy
from veupath_chatbot.services.experiment.helpers import extract_wdk_id

from .step_builders import build_steps_data_from_ast

logger = get_logger(__name__)

# ── Public API ──────────────────────────────────────────────────────────


@asynccontextmanager
async def wdk_error_boundary(operation: str) -> AsyncIterator[None]:
    """Wrap WDK operations with consistent error handling."""
    try:
        yield
    except AppError:
        raise
    except WDKError as e:
        logger.error(f"{operation} failed", error=str(e))
        raise
    except Exception as e:
        logger.error(f"{operation} failed", error=str(e))
        raise WDKError(f"Failed to {operation}: {e}") from e


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


async def fetch_and_convert(
    api: StrategyAPI,
    wdk_id: int,
) -> tuple[StrategyAST, bool]:
    """Fetch a WDK strategy and convert to internal AST.

    Normalizes parameters best-effort (failures are logged and swallowed).

    :returns: Tuple of (StrategyAST, is_saved).
    """
    wdk_strategy = await api.get_strategy(wdk_id)

    ast, steps_data = _build_snapshot_from_wdk(wdk_strategy)

    try:
        await _normalize_synced_parameters(ast, steps_data, api)
    except Exception as exc:
        logger.warning(
            "Parameter normalization failed, storing raw values",
            wdk_id=wdk_id,
            error=str(exc),
        )

    is_saved = extract_wdk_is_saved(wdk_strategy)
    return ast, is_saved


async def sync_to_projection(
    *,
    wdk_id: int,
    site_id: str,
    api: StrategyAPI,
    stream_repo: StreamRepository,
    user_id: UUID,
) -> StreamProjection:
    """Fetch a single WDK strategy and upsert into the CQRS layer.

    Shared by ``open_strategy`` and ``sync_all_wdk_strategies``.
    """
    ast, is_saved = await fetch_and_convert(api, wdk_id)
    plan = ast.to_dict()
    name = ast.name or f"WDK Strategy {wdk_id}"

    return await upsert_projection(
        stream_repo=stream_repo,
        user_id=user_id,
        site_id=site_id,
        wdk_id=wdk_id,
        name=name,
        plan=plan,
        record_type=ast.record_type,
        is_saved=is_saved,
        step_count=len(ast.get_all_steps()),
    )


async def upsert_projection(
    *,
    stream_repo: StreamRepository,
    user_id: UUID,
    site_id: str,
    wdk_id: int,
    name: str,
    plan: JSONObject,
    record_type: str | None,
    is_saved: bool,
    step_count: int = 0,
) -> StreamProjection:
    """Upsert a WDK strategy into the CQRS layer (create or update stream projection)."""
    existing = await stream_repo.get_by_wdk_strategy_id(user_id, wdk_id)
    if existing:
        await stream_repo.update_projection(
            existing.stream_id,
            name=name,
            plan=plan,
            record_type=record_type,
            wdk_strategy_id=wdk_id,
            wdk_strategy_id_set=True,
            is_saved=is_saved,
            is_saved_set=True,
            step_count=step_count,
        )
        proj = await stream_repo.get_projection(existing.stream_id)
    else:
        stream = await stream_repo.create(
            user_id=user_id,
            site_id=site_id,
            name=name,
        )
        await stream_repo.update_projection(
            stream.id,
            plan=plan,
            record_type=record_type,
            wdk_strategy_id=wdk_id,
            wdk_strategy_id_set=True,
            is_saved=is_saved,
            is_saved_set=True,
            step_count=step_count,
        )
        proj = await stream_repo.get_projection(stream.id)

    if proj is None:
        raise RuntimeError(f"Projection disappeared for WDK strategy {wdk_id}")
    return proj


# ── Step counts (WDK-backed) ───────────────────────────────────────────

_STEP_COUNTS_CACHE: OrderedDict[str, dict[str, int | None]] = OrderedDict()
_STEP_COUNTS_CACHE_MAX = 20


def _plan_cache_key(site_id: str, plan: JSONObject) -> str:
    payload = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{site_id}:{digest}"


async def compute_step_counts_for_plan(
    plan: JSONObject,
    strategy_ast: StrategyAST,
    site_id: str,
) -> dict[str, int | None]:
    """Compile a plan in WDK and return per-step result counts.

    Creates a temporary (unsaved) WDK strategy, fetches it once to read all
    estimatedSize values, then cleans up.  Results are cached by plan hash.
    """
    cache_key = _plan_cache_key(site_id, plan)
    cached = _STEP_COUNTS_CACHE.get(cache_key)
    if cached is not None:
        _STEP_COUNTS_CACHE.move_to_end(cache_key)
        return cached

    api = get_strategy_api(site_id)
    result = await compile_strategy(
        strategy_ast,
        api,
        site_id=site_id,
        resolve_record_type=True,
    )

    temp_strategy_id: int | None = None
    try:
        created = await api.create_strategy(
            step_tree=result.step_tree,
            name="Pathfinder step counts",
            description=None,
            is_internal=True,
        )
        temp_strategy_id = extract_wdk_id(created)
    except Exception:
        temp_strategy_id = None

    counts: dict[str, int | None] = {step.local_id: None for step in result.steps}

    if temp_strategy_id is not None:
        try:
            wdk_strategy = await api.get_strategy(temp_strategy_id)
            if isinstance(wdk_strategy, dict):
                steps_dict = wdk_strategy.get("steps")
                if isinstance(steps_dict, dict):
                    for step in result.steps:
                        step_info = steps_dict.get(str(step.wdk_step_id))
                        if isinstance(step_info, dict):
                            estimated = step_info.get("estimatedSize")
                            if isinstance(estimated, int):
                                counts[step.local_id] = estimated
        except Exception as e:
            logger.warning("Failed to read counts from strategy payload", error=str(e))

    await delete_temp_strategy(api, temp_strategy_id)

    _STEP_COUNTS_CACHE[cache_key] = counts
    if len(_STEP_COUNTS_CACHE) > _STEP_COUNTS_CACHE_MAX:
        _STEP_COUNTS_CACHE.popitem(last=False)

    return counts


# ── WDK → AST conversion (internal) ────────────────────────────────────


def _extract_record_type(wdk_strategy: JSONObject) -> str:
    """Extract the record type (urlSegment) from a WDK strategy payload."""
    value = wdk_strategy.get("recordClassName")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(
        f"WDK strategy is missing a valid 'recordClassName' "
        f"(got {type(value).__name__}: {value!r})"
    )


def _get_step_info(steps: JSONObject, step_id: int) -> JSONObject:
    """Look up a step object from the WDK ``steps`` dict."""
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
    """Extract the result count from a WDK step object."""
    value = step_info.get("estimatedSize")
    if isinstance(value, int):
        return value
    return None


def _build_node_from_wdk(
    step_tree: JSONObject,
    steps: JSONObject,
    record_type: str,
) -> PlanStepNode:
    """Recursively build a ``PlanStepNode`` tree from WDK stepTree + steps."""
    step_id_value = step_tree.get("stepId")
    if not isinstance(step_id_value, int):
        raise ValueError(
            f"Expected int 'stepId' in stepTree node, got "
            f"{type(step_id_value).__name__}: {step_id_value!r}"
        )
    step_id: int = step_id_value

    step_info = _get_step_info(steps, step_id)

    search_name_value = step_info.get("searchName")
    if not isinstance(search_name_value, str) or not search_name_value:
        raise ValueError(
            f"Step {step_id} is missing a valid 'searchName' "
            f"(got {type(search_name_value).__name__}: {search_name_value!r})"
        )
    search_name: str = search_name_value

    search_config_value = step_info.get("searchConfig")
    if not isinstance(search_config_value, dict):
        raise ValueError(f"Step {step_id} is missing 'searchConfig'")
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

    The steps list is used only for parameter normalization enrichment —
    steps are derived from plan at read time and not persisted.
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
