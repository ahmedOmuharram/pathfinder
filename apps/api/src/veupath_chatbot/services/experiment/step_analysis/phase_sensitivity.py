"""Phase 4: Parameter sensitivity -- sweep numeric params across their range."""

import asyncio
import copy
from typing import TypedDict

from veupath_chatbot.domain.strategy.tree import collect_dict_leaves, walk_dict_tree
from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.helpers import ProgressCallback, safe_float
from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _evaluate_tree_against_controls,
    _extract_eval_counts,
    _f1_from_counts,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _node_id,
)
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    ParameterSensitivity,
    ParameterSweepPoint,
    to_json,
)

SENSITIVITY_SWEEP_POINTS = 5

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


async def _discover_numeric_params(
    site_id: str,
    record_type: str,
    leaf: JSONObject,
) -> list[_NumericParamSpec]:
    """Discover numeric parameters on a leaf from WDK metadata."""
    search_name = str(leaf.get("searchName", ""))
    if not search_name:
        return []

    api = get_strategy_api(site_id)
    try:
        details = await api.client.get_search_details(record_type, search_name)
    except Exception as exc:
        logger.warning(
            "Failed to fetch search details for numeric param discovery",
            search_name=search_name,
            record_type=record_type,
            error=str(exc),
        )
        return []

    search_data = details.get("searchData") if isinstance(details, dict) else None
    if not isinstance(search_data, dict):
        return []

    params = search_data.get("parameters")
    if not isinstance(params, list):
        return []

    result: list[_NumericParamSpec] = []
    node_params = leaf.get("parameters", {})
    if not isinstance(node_params, dict):
        node_params = {}

    for p in params:
        if not isinstance(p, dict):
            continue
        pname = str(p.get("name", ""))
        ptype = str(p.get("type", ""))
        if ptype not in ("number", "string"):
            continue
        is_number = p.get("isNumber") is True or ptype == "number"
        if not is_number:
            continue

        min_val = _safe_float(p.get("min"))
        max_val = _safe_float(p.get("max"))
        current = _safe_float(node_params.get(pname))
        initial = _safe_float(p.get("initialDisplayValue"))
        ref = current if current is not None else initial

        if min_val is None:
            min_val = (
                0.0 if (ref is not None and ref >= 0) else (ref * 10 if ref else 0.0)
            )
        if max_val is None:
            max_val = ref * 10 if (ref is not None and ref > 0) else 100.0
        if min_val >= max_val:
            max_val = min_val + 1.0

        result.append(
            {
                "name": pname,
                "min": min_val,
                "max": max_val,
                "current": ref if ref is not None else (min_val + max_val) / 2,
            }
        )

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
    return (
        name_l.endswith("_lower") or name_l.endswith("_min") or name_l.startswith("min")
    )


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
    else:
        effective_min = max(min_val, partner_current)
        if effective_min >= max_val:
            effective_min = partner_current
        return effective_min, max_val


_MINIMUM_F1_IMPROVEMENT = 0.0


async def sweep_parameters(
    *,
    site_id: str,
    record_type: str,
    tree: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    controls_value_format: ControlValueFormat,
    positive_controls: list[str],
    negative_controls: list[str],
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

    # Deduplicate: only sweep unique (searchName, param) combinations.
    # When multiple leaves share the same search, sweep only the first one
    # since they would produce identical results.
    seen_search_params: set[str] = set()
    all_specs: list[tuple[JSONObject, _NumericParamSpec, list[_NumericParamSpec]]] = []

    for leaf in leaves:
        search_name = str(leaf.get("searchName", ""))
        params = await _discover_numeric_params(site_id, record_type, leaf)
        for spec in params:
            dedup_key = f"{search_name}:{spec['name']}"
            if dedup_key in seen_search_params:
                logger.debug(
                    "Skipping duplicate sweep",
                    search=search_name,
                    param=spec["name"],
                )
                continue
            seen_search_params.add(dedup_key)
            all_specs.append((leaf, spec, params))

    if not all_specs:
        return []

    results: list[ParameterSensitivity] = []
    sem = asyncio.Semaphore(3)
    total_params = len(all_specs)

    for pi, (leaf, spec, leaf_all_params) in enumerate(all_specs):
        lid = _node_id(leaf)
        pname = str(spec["name"])
        min_val = spec["min"]
        max_val = spec["max"]
        current = spec["current"]

        # Constrain sweep range for paired min/max bound parameters
        partner_spec = _find_bound_partner(pname, leaf_all_params)
        partner_current: float | None = None
        if partner_spec is not None:
            partner_current = partner_spec["current"]
            min_val, max_val = _constrain_sweep_range(
                pname, min_val, max_val, partner_current
            )
            if min_val >= max_val:
                max_val = min_val + 1.0
            # Clamp current into the constrained range so the sweep is sensible
            current = max(min_val, min(max_val, current))

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

        sweep_points: list[ParameterSweepPoint] = []

        async def _eval_value(
            val: float,
            _lid: str = lid,
            _pname: str = pname,
        ) -> ParameterSweepPoint | None:
            modified = copy.deepcopy(tree)

            def _patch_node(node: JSONObject) -> None:
                if _node_id(node) == _lid:
                    params = node.get("parameters")
                    if not isinstance(params, dict):
                        params = {}
                        node["parameters"] = params
                    params[_pname] = str(val)

            walk_dict_tree(modified, _patch_node)

            try:
                async with sem:
                    raw = await _evaluate_tree_against_controls(
                        site_id=site_id,
                        record_type=record_type,
                        tree=modified,
                        controls_search_name=controls_search_name,
                        controls_param_name=controls_param_name,
                        controls_value_format=controls_value_format,
                        positive_controls=positive_controls,
                        negative_controls=negative_controls,
                    )
            except Exception as exc:
                logger.warning(
                    "Sensitivity sweep point failed",
                    step=_lid,
                    param=_pname,
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

        tasks = [_eval_value(v) for v in sweep_values]
        points = await asyncio.gather(*tasks)
        sweep_points = [p for p in points if p is not None]
        sweep_points.sort(key=lambda p: p.value)

        # Pick the best point, but only recommend a change if the F1
        # improvement is meaningful (> threshold). This prevents noisy
        # recommendations when multiple values score similarly.
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
        if best_point and abs(recommended_value - current) > 1e-6 and cur_point:
            recommendation = (
                f"Changing {pname} from {current:.4g} to {recommended_value:.4g} "
                f"changes recall {cur_point.recall:.0%} -> {best_point.recall:.0%}"
                f" and FPR {cur_point.fpr:.0%} -> {best_point.fpr:.0%}"
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
                        "parameterSensitivity": to_json(ps),
                    },
                }
            )

    logger.info("Parameter sensitivity complete", count=len(results))
    return results
