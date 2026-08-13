"""Domain parameter specifications — pure types, no I/O."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pathfinder.domain.parameters.values import (
    ParamValue,
    as_param_kind,
    from_decoded,
)
from pathfinder.domain.parameters.wdk_vocab import WDKVocabulary, vocab_keys
from pathfinder.platform.types import JSONObject


@dataclass(frozen=True)
class ParamSpecNormalized:
    """Canonical representation of a WDK parameter spec."""

    name: str
    param_type: str
    allow_empty_value: bool = False
    min_selected_count: int | None = None
    max_selected_count: int | None = None
    vocabulary: WDKVocabulary | None = None
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
    """Return the dict that holds the parameters from a WDK or discovery payload."""
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
    """Sort param names so that a parent comes before the params it controls.

    A cycle falls back to lexical order.
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
    """Return the values of dependent params that are absent from their vocabulary.

    The vocabulary must already be refreshed. Empty and missing values are skipped.
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
        allowed = vocab_keys(spec.vocabulary)
        bad = [str(v) for v in _value_as_list(value) if str(v) not in allowed]
        if bad:
            violations.append((name, bad))
    return violations


def _value_as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return [value]


def fill_hidden_required_defaults(
    param_specs: dict[str, ParamSpecNormalized],
    parameters: Mapping[str, ParamValue],
) -> dict[str, ParamValue]:
    """Fill hidden required params from their fixed ``initial_display_value``.

    WDK rejects a search without these params, but the model cannot set them.
    Visible required params are never auto-filled.
    """
    filled: dict[str, ParamValue] = dict(parameters)
    for name, spec in param_specs.items():
        if (
            not spec.is_visible
            and not spec.allow_empty_value
            and name not in filled
            and spec.initial_display_value is not None
        ):
            filled[name] = from_decoded(
                as_param_kind(spec.param_type), spec.initial_display_value
            )
    return filled


def find_missing_required_params(
    param_specs: dict[str, ParamSpecNormalized],
    parameters: JSONObject,
) -> list[str]:
    """Return the names of required parameters that are missing or empty."""
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
