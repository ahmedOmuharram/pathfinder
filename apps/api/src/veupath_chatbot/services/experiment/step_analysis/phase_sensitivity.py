"""Phase 4: Parameter sensitivity -- sweep numeric params across their range."""

import asyncio
import copy
from typing import TypedDict

from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
    adapt_param_specs_from_search,
)
from veupath_chatbot.domain.strategy.tree import collect_dict_leaves, walk_dict_tree
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import (
    ControlsContext,
    ProgressCallback,
    safe_float,
)
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _extract_eval_counts,
    _f1_from_counts,
    run_controls_against_tree,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _node_id,
)
from veupath_chatbot.services.experiment.types import (
    ParameterSensitivity,
    ParameterSweepPoint,
)

SENSITIVITY_SWEEP_POINTS = 5

_FLOAT_COMPARISON_EPSILON = 1e-6

logger = get_logger(__name__)


class _NumericParamSpec(TypedDict):
    """Type-safe dict for a discovered numeric parameter."""

    name: str
    min: float
    max: float
    current: float


def _safe_float(v: object) -> float | None:
    """Convert to float, returning ``None`` for missing/unparseable values.

    Delegates to :func:`safe_float` for the actual conversion (including
    ``inf``/``nan`` rejection) but preserves ``None`` semantics for callers
    that need to distinguish "missing" from zero.
    """
    if v is None:
        return None
    # Use a sentinel that safe_float cannot produce from valid input.
    # safe_float rejects inf/nan, so inf is safe as a "not converted" marker.
    sentinel = float("inf")
    result = safe_float(v, default=sentinel)
    if result == sentinel:
        return None
    return result


def _build_param_spec(
    spec: ParamSpecNormalized,
    node_params: JSONObject,
) -> _NumericParamSpec | None:
    """Build a numeric param spec from a normalized spec, or None if not numeric."""
    if spec.param_type not in ("number", "string"):
        return None
    if not (spec.is_number or spec.param_type == "number"):
        return None

    min_val = spec.min_value
    max_val = spec.max_value
    current = _safe_float(node_params.get(spec.name))
    initial = _safe_float(spec.initial_display_value)
    ref = current if current is not None else initial

    if min_val is None:
        min_val = 0.0 if (ref is not None and ref >= 0) else (ref * 10 if ref else 0.0)
    if max_val is None:
        max_val = ref * 10 if (ref is not None and ref > 0) else 100.0
    if min_val >= max_val:
        max_val = min_val + 1.0

    return {
        "name": spec.name,
        "min": min_val,
        "max": max_val,
        "current": ref if ref is not None else (min_val + max_val) / 2,
    }


async def _fetch_search_specs(
    site_id: str,
    record_type: str,
    search_name: str,
) -> dict[str, ParamSpecNormalized] | None:
    """Fetch normalized WDK search parameter specs, or None on failure."""
    api = get_strategy_api(site_id)
    try:
        response = await api.client.get_search_details(record_type, search_name)
    except AppError as exc:
        logger.warning(
            "Failed to fetch search details for numeric param discovery",
            search_name=search_name,
            record_type=record_type,
            error=str(exc),
        )
        return None
    return adapt_param_specs_from_search(response.search_data)


async def _discover_numeric_params(
    site_id: str,
    record_type: str,
    leaf: JSONObject,
) -> list[_NumericParamSpec]:
    """Discover numeric parameters on a leaf from WDK metadata."""
    search_name = str(leaf.get("searchName", ""))
    if not search_name:
        return []

    specs = await _fetch_search_specs(site_id, record_type, search_name)
    if specs is None:
        return []

    node_params = leaf.get("parameters", {})
    if not isinstance(node_params, dict):
        node_params = {}

    result: list[_NumericParamSpec] = []
    for spec in specs.values():
        built = _build_param_spec(spec, node_params)
        if built is not None:
            result.append(built)

    return result


def _generate_sweep_values(
    min_val: float,
    max_val: float,
    current: float,
    n: int = SENSITIVITY_SWEEP_POINTS,
) -> list[float]:
    """Generate sweep values including the current value and endpoints."""
    step = (max_val - min_val) / (n - 1) if n > 1 else 0
    values = [min_val + i * step for i in range(n)]
    if current not in values:
        values.append(current)
        values.sort()
    return values


def _find_bound_partner(
    pname: str, all_param_specs: list[_NumericParamSpec]
) -> _NumericParamSpec | None:
    """Find the paired lower/upper bound parameter for a given param.

    Detects naming patterns:
      - ``foo_lower`` <-> ``foo_upper``
      - ``foo_min``   <-> ``foo_max``
      - ``MinFoo``    <-> ``MaxFoo``
      - ``min_foo``   <-> ``max_foo``
    """
    name_lower = pname.lower()

    for suffix_a, suffix_b in [
        ("_lower", "_upper"),
        ("_upper", "_lower"),
        ("_min", "_max"),
        ("_max", "_min"),
    ]:
        if name_lower.endswith(suffix_a):
            stem = pname[: len(pname) - len(suffix_a)]
            candidate = stem + suffix_b
            # Try original casing first, then lowercase match
            for s in all_param_specs:
                sn = str(s["name"])
                if sn == candidate or sn.lower() == candidate.lower():
                    return s
            break

    for prefix_a, prefix_b in [
        ("min", "max"),
        ("max", "min"),
        ("Min", "Max"),
        ("Max", "Min"),
    ]:
        if pname.startswith(prefix_a) and len(pname) > len(prefix_a):
            rest = pname[len(prefix_a) :]
            candidate = prefix_b + rest
            for s in all_param_specs:
                if str(s["name"]) == candidate:
                    return s
            break

    return None


def _is_lower_bound(pname: str) -> bool:
    """Determine if a parameter represents a lower bound."""
    name_l = pname.lower()
    return name_l.endswith(("_lower", "_min")) or name_l.startswith("min")


def _constrain_sweep_range(
    pname: str,
    min_val: float,
    max_val: float,
    partner_current: float | None,
) -> tuple[float, float]:
    """Constrain sweep range for a bound parameter based on its partner's value.

    For lower-bound params: sweep from min_val to min(max_val, partner_current).
    For upper-bound params: sweep from max(min_val, partner_current) to max_val.
    """
    if partner_current is None:
        return min_val, max_val

    if _is_lower_bound(pname):
        effective_max = min(max_val, partner_current)
        if effective_max <= min_val:
            effective_max = partner_current
        return min_val, effective_max
    effective_min = max(min_val, partner_current)
    if effective_min >= max_val:
        effective_min = partner_current
    return effective_min, max_val


_MINIMUM_F1_IMPROVEMENT = 0.0


def _pick_recommendation(
    pname: str,
    current: float,
    sweep_points: list[ParameterSweepPoint],
    partner_current: float | None,
) -> tuple[float, str]:
    """Select the recommended value and build a human-readable recommendation string.

    Returns ``(recommended_value, recommendation_text)``.
    """
    cur_point = (
        min(sweep_points, key=lambda p: abs(p.value - current))
        if sweep_points
        else None
    )
    cur_f1 = cur_point.f1 if cur_point else 0.0

    best_point = max(sweep_points, key=lambda p: p.f1) if sweep_points else None
    improvement = (best_point.f1 - cur_f1) if best_point else 0.0

    if best_point and improvement > _MINIMUM_F1_IMPROVEMENT:
        recommended_value = best_point.value
    else:
        recommended_value = current
        best_point = cur_point

    # For bound params, validate the recommendation doesn't violate its partner
    if (
        partner_current is not None
        and best_point
        and (
            (_is_lower_bound(pname) and recommended_value > partner_current)
            or (not _is_lower_bound(pname) and recommended_value < partner_current)
        )
    ):
        recommended_value = current

    recommendation = ""
    if (
        best_point
        and abs(recommended_value - current) > _FLOAT_COMPARISON_EPSILON
        and cur_point
    ):
        recommendation = (
            f"Changing {pname} from {current:.4g} to {recommended_value:.4g} "
            f"changes recall {cur_point.recall:.0%} -> {best_point.recall:.0%}"
            f" and FPR {cur_point.fpr:.0%} -> {best_point.fpr:.0%}"
        )

    return recommended_value, recommendation


def _prepare_sweep_range(
    spec: _NumericParamSpec, leaf_all_params: list[_NumericParamSpec]
) -> tuple[float, float, float, _NumericParamSpec | None, float | None]:
    """Constrain the sweep range for a parameter, respecting bound partners.

    Returns ``(min_val, max_val, current, partner_spec, partner_current)``.
    """
    pname = str(spec["name"])
    min_val = spec["min"]
    max_val = spec["max"]
    current = spec["current"]

    partner_spec = _find_bound_partner(pname, leaf_all_params)
    partner_current: float | None = None
    if partner_spec is not None:
        partner_current = partner_spec["current"]
        min_val, max_val = _constrain_sweep_range(
            pname, min_val, max_val, partner_current
        )
        if min_val >= max_val:
            max_val = min_val + 1.0
        current = max(min_val, min(max_val, current))

    return min_val, max_val, current, partner_spec, partner_current


async def _collect_sweep_specs(
    site_id: str,
    record_type: str,
    leaves: list[JSONObject],
) -> list[tuple[JSONObject, _NumericParamSpec, list[_NumericParamSpec]]]:
    """Collect deduplicated (leaf, spec, all_params) tuples for sweeping."""
    seen: set[str] = set()
    result: list[tuple[JSONObject, _NumericParamSpec, list[_NumericParamSpec]]] = []
    for leaf in leaves:
        search_name = str(leaf.get("searchName", ""))
        params = await _discover_numeric_params(site_id, record_type, leaf)
        for spec in params:
            dedup_key = f"{search_name}:{spec['name']}"
            if dedup_key in seen:
                logger.debug(
                    "Skipping duplicate sweep",
                    search=search_name,
                    param=spec["name"],
                )
                continue
            seen.add(dedup_key)
            result.append((leaf, spec, params))
    return result


async def _eval_sweep_value(
    val: float,
    lid: str,
    pname: str,
    tree: JSONObject,
    sem: asyncio.Semaphore,
    ctx: ControlsContext,
) -> ParameterSweepPoint | None:
    """Evaluate a single parameter value by running controls against a patched tree."""
    modified = copy.deepcopy(tree)

    def _patch_node(node: JSONObject) -> None:
        if _node_id(node) == lid:
            params = node.get("parameters")
            if not isinstance(params, dict):
                params = {}
                node["parameters"] = params
            params[pname] = str(val)

    walk_dict_tree(modified, _patch_node)

    try:
        async with sem:
            raw = await run_controls_against_tree(ctx, modified)
    except AppError as exc:
        logger.warning(
            "Sensitivity sweep point failed",
            step=lid,
            param=pname,
            value=val,
            error=str(exc),
        )
        return None

    counts = _extract_eval_counts(raw)
    recall = counts.pos_hits / counts.pos_total if counts.pos_total > 0 else 0.0
    fpr = counts.neg_hits / counts.neg_total if counts.neg_total > 0 else 0.0

    return ParameterSweepPoint(
        value=round(val, 6),
        positive_hits=counts.pos_hits,
        negative_hits=counts.neg_hits,
        total_results=counts.total_results,
        recall=recall,
        fpr=fpr,
        f1=_f1_from_counts(counts),
    )


async def sweep_parameters(
    ctx: ControlsContext,
    tree: JSONObject,
    progress_callback: ProgressCallback | None = None,
) -> list[ParameterSensitivity]:
    """Sweep numeric params on each leaf across their WDK-declared range.

    Respects paired min/max bound parameters, deduplicates identical
    searches across leaves, and only recommends changes when the
    improvement is meaningful.

    :param tree: ``PlanStepNode``-shaped dict.
    :returns: One :class:`ParameterSensitivity` per numeric param.
    """
    leaves = collect_dict_leaves(tree)
    if not leaves:
        return []

    all_specs = await _collect_sweep_specs(ctx.site_id, ctx.record_type, leaves)
    if not all_specs:
        return []

    results: list[ParameterSensitivity] = []
    sem = asyncio.Semaphore(3)
    total_params = len(all_specs)

    for pi, (leaf, spec, leaf_all_params) in enumerate(all_specs):
        lid = _node_id(leaf)
        pname = str(spec["name"])
        min_val, max_val, current, partner_spec, partner_current = _prepare_sweep_range(
            spec, leaf_all_params
        )
        sweep_values = _generate_sweep_values(min_val, max_val, current)

        if progress_callback:
            constraint_note = ""
            if partner_spec is not None:
                partner_name = str(partner_spec["name"])
                constraint_note = f" (bounded by {partner_name}={partner_current})"
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "sensitivity",
                        "message": (
                            f"Sweeping {pname} on {lid} "
                            f"({pi + 1}/{total_params}, {len(sweep_values)} points)"
                            f"{constraint_note}"
                        ),
                        "current": pi + 1,
                        "total": total_params,
                    },
                }
            )

        tasks = [_eval_sweep_value(v, lid, pname, tree, sem, ctx) for v in sweep_values]
        points = await asyncio.gather(*tasks)
        sweep_points = [p for p in points if p is not None]
        sweep_points.sort(key=lambda p: p.value)

        recommended_value, recommendation = _pick_recommendation(
            pname, current, sweep_points, partner_current
        )

        ps = ParameterSensitivity(
            step_id=lid,
            param_name=pname,
            current_value=current,
            sweep_points=sweep_points,
            recommended_value=recommended_value,
            recommendation=recommendation,
        )
        results.append(ps)

        if progress_callback:
            await progress_callback(
                {
                    "type": "step_analysis_progress",
                    "data": {
                        "phase": "sensitivity",
                        "message": recommendation
                        or f"Parameter {pname}: no change recommended",
                        "current": pi + 1,
                        "total": total_params,
                        "parameterSensitivity": ps.model_dump(by_alias=True),
                    },
                }
            )

    logger.info("Parameter sensitivity complete", count=len(results))
    return results
