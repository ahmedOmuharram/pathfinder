"""Domain parameter specifications — pure types, no I/O."""

from __future__ import annotations

from dataclasses import dataclass

from pathfinder.platform.types import JSONArray, JSONObject


@dataclass(frozen=True)
class ParamSpecNormalized:
    """Canonical representation of a WDK parameter spec."""

    name: str
    param_type: str
    allow_empty_value: bool = False
    min_selected_count: int | None = None
    max_selected_count: int | None = None
    vocabulary: JSONObject | JSONArray | None = None
    count_only_leaves: bool = False
    is_number: bool = False
    min: float | None = None
    max: float | None = None
    increment: float | None = None
    max_length: int | None = None
    display_type: str = ""
    is_visible: bool = True
    group: str = ""
    dependent_params: tuple[str, ...] = ()
    help: str | None = None
    initial_display_value: str | None = None


def unwrap_search_data(details: JSONObject | None) -> JSONObject | None:
    """Normalize WDK/discovery payload shape to the dict that contains parameters.

    :param details: Search details from WDK/discovery.
    :returns: Search data dict or None.
    """
    if not isinstance(details, dict):
        return None
    search_data_raw = details.get("searchData")
    if isinstance(search_data_raw, dict):
        return search_data_raw
    return details


def find_input_step_param(specs: dict[str, ParamSpecNormalized]) -> str | None:
    for spec in specs.values():
        if spec.param_type == "input-step":
            return spec.name
    return None


def topological_fill_order(specs: dict[str, ParamSpecNormalized]) -> list[str]:
    """Kahn topological sort of param names by dependent_params edges.

    Parents (params whose ``dependent_params`` lists others) come before
    their children. Cycles fall back to lexical order.
    """
    depends_on: dict[str, list[str]] = {}
    controls: dict[str, list[str]] = {name: [] for name in specs}
    for name, spec in specs.items():
        for dep in spec.dependent_params:
            controls.setdefault(name, []).append(dep)
            depends_on.setdefault(dep, []).append(name)
    in_degree = {name: len(depends_on.get(name, [])) for name in specs}
    queue = [n for n in specs if in_degree[n] == 0]
    fill: list[str] = []
    while queue:
        node = queue.pop(0)
        fill.append(node)
        for child in controls.get(node, []):
            if child in in_degree:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
    fill.extend(n for n in specs if n not in fill)
    return fill


def find_dependent_value_violations(
    param_specs: dict[str, ParamSpecNormalized],
    parameters: JSONObject,
) -> list[tuple[str, list[str]]]:
    """Return ``[(param_name, invalid_values)]`` for dependent params with
    values not present in the (already-refreshed) vocabulary.

    Only applies to params whose name appears in some other spec's
    ``dependent_params`` list; ie this is a *child of a parent that
    controls vocab*. Empty / missing values are skipped — those are
    handled by ``find_missing_required_params``.
    """
    dependent_names: set[str] = {
        dep for spec in param_specs.values() for dep in spec.dependent_params
    }
    violations: list[tuple[str, list[str]]] = []
    for name in dependent_names:
        spec = param_specs.get(name)
        if spec is None or spec.vocabulary is None:
            continue
        value = parameters.get(name)
        if value in (None, "", [], {}):
            continue
        allowed = _vocab_keys(spec.vocabulary)
        bad = [str(v) for v in _value_as_list(value) if str(v) not in allowed]
        if bad:
            violations.append((name, bad))
    return violations


def _vocab_keys(vocab: JSONObject | JSONArray) -> set[str]:
    if isinstance(vocab, list):
        out: set[str] = set()
        for item in vocab:
            if isinstance(item, list) and item:
                out.add(str(item[0]))
            elif isinstance(item, dict) and "value" in item:
                out.add(str(item["value"]))
            else:
                out.add(str(item))
        return out
    return {str(k) for k in vocab}


def _value_as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return [value]


def find_missing_required_params(
    param_specs: dict[str, ParamSpecNormalized],
    parameters: JSONObject,
) -> list[str]:
    """Find required parameters that are missing or empty in the given values.

    Shared by ``validation.py`` and ``param_validation.py`` to keep the
    required-check logic in a single place.

    :param param_specs: Normalized parameter specs (from
        ``adapt_param_specs_from_search``).
    :param parameters: Parameter values to check.
    :returns: List of missing required parameter names.
    """
    missing: list[str] = []
    for name, spec in param_specs.items():
        is_required = not spec.allow_empty_value or (
            spec.min_selected_count is not None and spec.min_selected_count >= 1
        )
        if not is_required:
            continue
        if name not in parameters:
            missing.append(name)
            continue
        value = parameters.get(name)
        if spec.param_type == "multi-pick-vocabulary":
            if value in (None, "", "[]") or (
                isinstance(value, list) and len(value) == 0
            ):
                missing.append(name)
            continue
        if value in (None, "", [], {}):
            missing.append(name)

    return missing
