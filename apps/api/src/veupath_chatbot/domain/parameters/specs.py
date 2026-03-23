"""Adapters for WDK parameter specifications."""

from __future__ import annotations

from dataclasses import dataclass

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKBaseParameter
from veupath_chatbot.platform.types import JSONArray, JSONObject


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
    min_value: float | None = None
    max_value: float | None = None
    increment: float | None = None
    max_length: int | None = None
    display_type: str = ""
    is_visible: bool = True
    group: str = ""
    dependent_params: tuple[str, ...] = ()
    help: str | None = None
    initial_display_value: str | None = None

    @classmethod
    def from_wdk(cls, param: WDKBaseParameter) -> ParamSpecNormalized:
        """Convert a typed WDK parameter to the canonical spec."""
        return cls(
            name=param.name,
            param_type=param.type,
            allow_empty_value=param.allow_empty_value,
            min_selected_count=param.min_selected_count,
            max_selected_count=param.max_selected_count,
            vocabulary=param.vocabulary,
            count_only_leaves=param.count_only_leaves,
            is_number=param.is_number,
            min_value=float(param.min) if param.min is not None else None,
            max_value=float(param.max) if param.max is not None else None,
            increment=float(param.increment) if param.increment is not None else None,
            max_length=param.length if param.length > 0 else None,
            display_type=param.display_type,
            is_visible=param.is_visible,
            group=param.group,
            dependent_params=tuple(param.dependent_params),
            help=param.help,
            initial_display_value=param.initial_display_value,
        )


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


def adapt_param_specs_from_search(search: WDKSearch) -> dict[str, ParamSpecNormalized]:
    """Build normalized param specs from a typed WDK search."""
    if not search.parameters:
        return {}
    return {p.name: ParamSpecNormalized.from_wdk(p) for p in search.parameters}
