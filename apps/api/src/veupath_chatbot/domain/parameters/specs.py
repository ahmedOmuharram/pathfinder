"""Adapters for WDK parameter specifications."""

from __future__ import annotations

from dataclasses import dataclass

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.integrations.veupathdb.wdk_parameters import WDKBaseParameter
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


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
        vocabulary = param.vocabulary if hasattr(param, "vocabulary") else None
        min_sel = getattr(param, "min_selected_count", None)
        max_sel = getattr(param, "max_selected_count", None)
        if isinstance(max_sel, int) and max_sel < 0:
            max_sel = None
        is_number = getattr(param, "is_number", False)
        min_val = getattr(param, "min", None)
        max_val = getattr(param, "max", None)
        increment = getattr(param, "increment", None)
        length = getattr(param, "length", None)
        max_length = length if isinstance(length, int) and length > 0 else None
        count_only_leaves = getattr(param, "count_only_leaves", False)
        display_type = getattr(param, "display_type", "")
        return cls(
            name=param.name,
            param_type=param.type,
            allow_empty_value=param.allow_empty_value,
            min_selected_count=min_sel if isinstance(min_sel, int) else None,
            max_selected_count=max_sel if isinstance(max_sel, int) else None,
            vocabulary=vocabulary,
            count_only_leaves=bool(count_only_leaves),
            is_number=bool(is_number),
            min_value=float(min_val) if isinstance(min_val, (int, float)) else None,
            max_value=float(max_val) if isinstance(max_val, (int, float)) else None,
            increment=float(increment) if isinstance(increment, (int, float)) else None,
            max_length=max_length,
            display_type=str(display_type),
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


def extract_param_specs(payload: JSONObject) -> JSONArray:
    """Extract parameter spec dicts from a WDK payload.

    Supports the canonical WDK paths (in priority order):
      1. ``payload["parameters"]`` -- list or dict
      2. ``payload["paramMap"]`` -- dict (name -> spec)
      3. ``payload["searchConfig"]["parameters"]`` -- list or dict
      4. ``payload["searchConfig"]["paramMap"]`` -- dict
    """
    search_config_raw = payload.get("searchConfig")
    search_config = search_config_raw if isinstance(search_config_raw, dict) else {}

    candidates: list[JSONValue] = [
        payload.get("parameters"),
        payload.get("paramMap"),
        search_config.get("parameters"),
        search_config.get("paramMap"),
    ]
    params: JSONValue = next((c for c in candidates if c), [])
    specs: JSONArray = []
    if isinstance(params, dict):
        for name, param in params.items():
            if isinstance(param, dict):
                specs.append({"name": name, **param})
    elif isinstance(params, list):
        for param in params:
            if isinstance(param, dict):
                specs.append(param)
    return specs


def _safe_float(raw: JSONValue) -> float | None:
    """Convert a raw JSON value to float, returning None on failure."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if not isinstance(raw, str):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _safe_int(raw: JSONValue) -> int | None:
    """Convert a raw JSON value to int, returning None on failure."""
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def adapt_param_specs(payload: JSONObject) -> dict[str, ParamSpecNormalized]:
    specs = extract_param_specs(payload or {})
    normalized: dict[str, ParamSpecNormalized] = {}
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        name_raw = spec.get("name")
        if not isinstance(name_raw, str):
            continue
        name = name_raw
        type_raw = spec.get("type") or spec.get("paramType")
        param_type = str(type_raw) if isinstance(type_raw, str) else ""
        allow_empty_raw = spec.get("allowEmptyValue") or spec.get("allowEmpty")
        allow_empty_value = bool(allow_empty_raw)
        min_selected = spec.get("minSelectedCount")
        max_selected = spec.get("maxSelectedCount")
        if isinstance(max_selected, int) and max_selected < 0:
            max_selected = None
        vocabulary_raw = spec.get("vocabulary")
        vocabulary: JSONObject | JSONArray | None = None
        if isinstance(vocabulary_raw, (dict, list)):
            vocabulary = vocabulary_raw

        # WDK StringParam can be numeric (isNumber=true on type="string")
        is_number_raw = spec.get("isNumber")
        is_number = bool(is_number_raw) if isinstance(is_number_raw, bool) else False

        # Numeric constraints: min/max/increment
        min_value = _safe_float(spec.get("min"))
        max_value = _safe_float(spec.get("max"))
        increment_raw = spec.get("increment")
        increment = _safe_float(
            increment_raw if increment_raw is not None else spec.get("step")
        )

        # String constraints: maxLength / length (0 means "no limit" in WDK)
        max_length_raw = spec.get("maxLength")
        max_length = _safe_int(
            max_length_raw if max_length_raw is not None else spec.get("length")
        )
        if max_length is not None and max_length <= 0:
            max_length = None

        # WDK UI metadata
        display_type = str(spec.get("displayType") or "")
        is_visible_raw = spec.get("isVisible")
        is_visible = bool(is_visible_raw) if isinstance(is_visible_raw, bool) else True
        group = str(spec.get("group") or "")
        dependent_params_raw = spec.get("dependentParams")
        dependent_params = (
            tuple(str(p) for p in dependent_params_raw)
            if isinstance(dependent_params_raw, list)
            else ()
        )
        help_text = spec.get("help")
        help_str = str(help_text) if isinstance(help_text, str) else None

        normalized[name] = ParamSpecNormalized(
            name=name,
            param_type=param_type,
            allow_empty_value=allow_empty_value,
            min_selected_count=min_selected if isinstance(min_selected, int) else None,
            max_selected_count=max_selected if isinstance(max_selected, int) else None,
            vocabulary=vocabulary,
            count_only_leaves=bool(spec.get("countOnlyLeaves")),
            is_number=is_number,
            min_value=min_value,
            max_value=max_value,
            increment=increment,
            max_length=max_length,
            display_type=display_type,
            is_visible=is_visible,
            group=group,
            dependent_params=dependent_params,
            help=help_str,
        )
    return normalized


def find_input_step_param(specs: dict[str, ParamSpecNormalized]) -> str | None:
    for spec in specs.values():
        if spec.param_type == "input-step":
            return spec.name
    return None


def find_missing_required_params(
    param_specs: JSONArray,
    parameters: JSONObject,
) -> list[str]:
    """Find required parameters that are missing or empty in the given values.

    Shared by ``validation.py`` and ``param_validation.py`` to keep the
    required-check logic in a single place.

    :param param_specs: Raw WDK parameter spec dicts.
    :param parameters: Parameter values to check.
    :returns: List of missing required parameter names.
    """
    required_specs: list[JSONObject] = []
    for p in param_specs:
        if not isinstance(p, dict):
            continue
        allow_empty_raw = p.get("allowEmptyValue")
        allow_empty = (
            bool(allow_empty_raw) if isinstance(allow_empty_raw, bool) else True
        )
        min_selected_raw = p.get("minSelectedCount")
        min_selected = min_selected_raw if isinstance(min_selected_raw, int) else 0
        if not allow_empty or min_selected >= 1:
            required_specs.append(p)

    missing: list[str] = []
    for spec in required_specs:
        if not isinstance(spec, dict):
            continue
        name_raw = spec.get("name")
        name = name_raw if isinstance(name_raw, str) else None
        if not name:
            continue
        if name not in parameters:
            missing.append(name)
            continue
        value = parameters.get(name)
        type_raw = spec.get("type")
        param_type = (type_raw if isinstance(type_raw, str) else "").lower()
        if param_type == "multi-pick-vocabulary":
            if value in (None, "", "[]") or (
                isinstance(value, list) and len(value) == 0
            ):
                missing.append(name)
            continue
        if value in (None, "", [], {}):
            missing.append(name)

    return missing


def adapt_param_specs_from_search(search: WDKSearch) -> dict[str, ParamSpecNormalized]:
    """Build normalized param specs from a typed WDK search.

    Typed equivalent of :func:`adapt_param_specs` -- uses ``from_wdk()``
    instead of manual dict extraction.
    """
    if not search.parameters:
        return {}
    return {p.name: ParamSpecNormalized.from_wdk(p) for p in search.parameters}
