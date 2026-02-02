"""Adapters for WDK parameter specifications."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParamSpecNormalized:
    """Canonical representation of a WDK parameter spec."""

    name: str
    param_type: str
    allow_empty_value: bool = False
    min_selected_count: int | None = None
    max_selected_count: int | None = None
    vocabulary: dict[str, Any] | list[Any] | None = None
    count_only_leaves: bool = False


def extract_param_specs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        payload.get("parameters"),
        payload.get("paramMap"),
        payload.get("parameterDetails"),
        payload.get("paramDetails"),
        (payload.get("searchConfig") or {}).get("parameters"),
        (payload.get("searchConfig") or {}).get("paramMap"),
        (payload.get("question") or {}).get("parameters"),
    ]
    params = next((c for c in candidates if c), [])
    specs: list[dict[str, Any]] = []
    if isinstance(params, dict):
        for name, param in params.items():
            if isinstance(param, dict):
                specs.append({"name": name, **param})
    elif isinstance(params, list):
        for param in params:
            if isinstance(param, dict):
                specs.append(param)
    return specs


def adapt_param_specs(payload: dict[str, Any]) -> dict[str, ParamSpecNormalized]:
    specs = extract_param_specs(payload or {})
    normalized: dict[str, ParamSpecNormalized] = {}
    for spec in specs:
        name = spec.get("name")
        if not name:
            continue
        param_type = spec.get("type") or spec.get("paramType") or ""
        allow_empty_value = bool(spec.get("allowEmptyValue") or spec.get("allowEmpty"))
        min_selected = spec.get("minSelectedCount")
        max_selected = spec.get("maxSelectedCount")
        if isinstance(max_selected, int) and max_selected < 0:
            max_selected = None
        normalized[str(name)] = ParamSpecNormalized(
            name=str(name),
            param_type=str(param_type),
            allow_empty_value=allow_empty_value,
            min_selected_count=min_selected if isinstance(min_selected, int) else None,
            max_selected_count=max_selected if isinstance(max_selected, int) else None,
            vocabulary=spec.get("vocabulary"),
            count_only_leaves=bool(spec.get("countOnlyLeaves")),
        )
    return normalized


def find_input_step_param(specs: dict[str, ParamSpecNormalized]) -> str | None:
    for spec in specs.values():
        if spec.param_type == "input-step":
            return spec.name
    return None

