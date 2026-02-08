"""Adapters for WDK parameter specifications."""

from dataclasses import dataclass

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


def extract_param_specs(payload: JSONObject) -> JSONArray:
    search_config_raw = payload.get("searchConfig")
    search_config = search_config_raw if isinstance(search_config_raw, dict) else {}
    question_raw = payload.get("question")
    question = question_raw if isinstance(question_raw, dict) else {}

    candidates: list[JSONValue] = [
        payload.get("parameters"),
        payload.get("paramMap"),
        payload.get("parameterDetails"),
        payload.get("paramDetails"),
        search_config.get("parameters"),
        search_config.get("paramMap"),
        question.get("parameters"),
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
        normalized[name] = ParamSpecNormalized(
            name=name,
            param_type=param_type,
            allow_empty_value=allow_empty_value,
            min_selected_count=min_selected if isinstance(min_selected, int) else None,
            max_selected_count=max_selected if isinstance(max_selected, int) else None,
            vocabulary=vocabulary,
            count_only_leaves=bool(spec.get("countOnlyLeaves")),
        )
    return normalized


def find_input_step_param(specs: dict[str, ParamSpecNormalized]) -> str | None:
    for spec in specs.values():
        if spec.param_type == "input-step":
            return spec.name
    return None
