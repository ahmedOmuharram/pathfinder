"""Shared validation and coercion helpers for parameter processing.

Used by ``ParameterCanonicalizer`` to produce decoded-form parameter
values (lists, dicts, scalars). The dispatch chain in ``process_value()``
validates and coerces per WDK param type; the canonicalizer applies
canonicalizer-specific post-processing (leaf enforcement, sentinel
rejection) on top.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.value_utils import decode_values
from pathfinder.domain.parameters.vocab_utils import match_vocab_value
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.types import JSONObject


def _safe_float(value: JsonValue) -> float | None:
    """Convert a raw JSON value to float, returning None on failure."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


_ParamHandler = Callable[["ParamSpecNormalized", "JsonValue"], "ProcessedParam"]

_RANGE_PAIR_LENGTH = 2

_NUMERIC_PARAM_TYPES = frozenset({"number", "number-range"})


@dataclass(frozen=True)
class MultiPickProcessed:
    value: list[str]
    kind: Literal["multi_pick"] = "multi_pick"


@dataclass(frozen=True)
class SinglePickProcessed:
    value: str
    kind: Literal["single_pick"] = "single_pick"


@dataclass(frozen=True)
class ScalarProcessed:
    value: str
    kind: Literal["scalar"] = "scalar"


@dataclass(frozen=True)
class RangeProcessed:
    value: JSONObject
    kind: Literal["range"] = "range"


@dataclass(frozen=True)
class FilterProcessed:
    value: JsonValue
    kind: Literal["filter"] = "filter"


@dataclass(frozen=True)
class InputDatasetProcessed:
    value: str
    kind: Literal["input_dataset"] = "input_dataset"


@dataclass(frozen=True)
class UnknownProcessed:
    value: JsonValue
    kind: Literal["unknown"] = "unknown"


@dataclass(frozen=True)
class EmptyProcessed:
    value: JsonValue
    kind: Literal["empty"] = "empty"


ProcessedParam = (
    MultiPickProcessed
    | SinglePickProcessed
    | ScalarProcessed
    | RangeProcessed
    | FilterProcessed
    | InputDatasetProcessed
    | UnknownProcessed
    | EmptyProcessed
)

# Param-type groupings (avoids duplicating string literals)
SCALAR_TYPES = frozenset({"number", "date", "timestamp", "string"})
RANGE_TYPES = frozenset({"number-range", "date-range"})

# -- public helpers ----------------------------------------------------------


def stringify(value: JsonValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def handle_empty(spec: ParamSpecNormalized, value: JsonValue) -> JsonValue:
    if spec.allow_empty_value:
        return ""
    raise ValidationError(
        title="Invalid parameter value",
        detail=f"Parameter '{spec.name}' requires a value.",
        errors=[{"param": spec.name}],
    )


def validate_multi_count(spec: ParamSpecNormalized, values: list[str]) -> None:
    if not values and spec.allow_empty_value:
        return
    min_count = spec.min_selected_count or 0
    max_count = spec.max_selected_count
    if len(values) < min_count:
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' requires at least {min_count} value(s).",
            errors=[{"param": spec.name, "value": list(values)}],
        )
    if max_count is not None and len(values) > max_count:
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' allows at most {max_count} value(s).",
            errors=[{"param": spec.name, "value": list(values)}],
        )


def validate_single_required(spec: ParamSpecNormalized) -> None:
    if spec.allow_empty_value:
        return
    min_count = spec.min_selected_count
    if min_count is not None and min_count <= 0:
        return
    raise ValidationError(
        title="Invalid parameter value",
        detail=f"Parameter '{spec.name}' requires a value.",
        errors=[{"param": spec.name}],
    )


def validate_numeric_range(spec: ParamSpecNormalized, numeric_value: float) -> None:
    """Validate a numeric value against min/max constraints if present."""
    if spec.min is not None and numeric_value < spec.min:
        raise ValidationError(
            title="Invalid parameter value",
            detail=(
                f"Parameter '{spec.name}' value {numeric_value} "
                f"is below minimum {spec.min}."
            ),
            errors=[{"param": spec.name, "value": numeric_value}],
        )
    if spec.max is not None and numeric_value > spec.max:
        raise ValidationError(
            title="Invalid parameter value",
            detail=(
                f"Parameter '{spec.name}' value {numeric_value} "
                f"exceeds maximum {spec.max}."
            ),
            errors=[{"param": spec.name, "value": numeric_value}],
        )


def validate_string_length(spec: ParamSpecNormalized, string_value: str) -> None:
    """Validate a string value against max_length constraint if present."""
    if spec.max_length is not None and len(string_value) > spec.max_length:
        raise ValidationError(
            title="Invalid parameter value",
            detail=(
                f"Parameter '{spec.name}' value exceeds maximum length "
                f"of {spec.max_length} characters."
            ),
            errors=[{"param": spec.name, "value": string_value}],
        )


# -- shared dispatch chain ---------------------------------------------------


def process_value(spec: ParamSpecNormalized, value: JsonValue) -> ProcessedParam:
    """Validate, decode, and coerce *value* according to *spec*.

    Returns a ``ProcessedParam`` whose ``kind`` tells the caller what
    output formatting to apply.  All validation errors are raised here
    so downstream formatters need not re-check.
    """
    if value is None:
        empty = handle_empty(spec, value)
        return EmptyProcessed(value=empty)

    handler = _DISPATCH_TABLE.get(spec.param_type)
    if handler is None:
        return UnknownProcessed(value=value)
    return handler(spec, value)


# -- per-type processors -----------------------------------------------------


def process_multi_pick(spec: ParamSpecNormalized, value: JsonValue) -> ProcessedParam:
    values = [stringify(v) for v in decode_values(value, spec.name)]
    matched: list[str] = [
        match_vocab_value(vocab=spec.vocabulary, param_name=spec.name, value=v)
        for v in values
    ]
    validate_multi_count(spec, matched)
    return MultiPickProcessed(value=matched)


def process_single_pick(spec: ParamSpecNormalized, value: JsonValue) -> ProcessedParam:
    decoded = decode_values(value, spec.name)
    if len(decoded) > 1:
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' allows only one value.",
            errors=[{"param": spec.name, "value": value}],
        )
    selected = stringify(decoded[0]) if decoded else ""
    if not selected:
        validate_single_required(spec)
        return SinglePickProcessed(value="")
    selected = match_vocab_value(
        vocab=spec.vocabulary, param_name=spec.name, value=selected
    )
    if not selected:
        validate_single_required(spec)
    return SinglePickProcessed(value=stringify(selected))


def process_scalar(spec: ParamSpecNormalized, value: JsonValue) -> ProcessedParam:
    if isinstance(value, (list, dict, tuple, set)):
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' must be a scalar value.",
            errors=[{"param": spec.name, "value": value}],
        )
    str_value = stringify(value)

    if spec.param_type in _NUMERIC_PARAM_TYPES or spec.is_number:
        parsed = _safe_float(value)
        if parsed is not None:
            validate_numeric_range(spec, parsed)

    if spec.param_type == "string" and spec.max_length is not None:
        validate_string_length(spec, str_value)

    return ScalarProcessed(value=str_value)


def process_range(spec: ParamSpecNormalized, value: JsonValue) -> ProcessedParam:
    range_dict: JSONObject
    if isinstance(value, dict):
        range_dict = value
    elif isinstance(value, (list, tuple)) and len(value) == _RANGE_PAIR_LENGTH:
        range_dict = {"min": value[0], "max": value[1]}
    else:
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' must be a range.",
            errors=[{"param": spec.name, "value": value}],
        )

    if spec.param_type in _NUMERIC_PARAM_TYPES:
        for key in ("min", "max"):
            endpoint = range_dict.get(key)
            if endpoint is not None:
                parsed = _safe_float(endpoint)
                if parsed is not None:
                    validate_numeric_range(spec, parsed)

    return RangeProcessed(value=range_dict)


def process_filter(spec: ParamSpecNormalized, value: JsonValue) -> ProcessedParam:
    _ = spec
    if isinstance(value, (dict, list)):
        return FilterProcessed(value=value)
    return FilterProcessed(value=stringify(value))


def process_input_dataset(
    spec: ParamSpecNormalized, value: JsonValue
) -> ProcessedParam:
    if isinstance(value, list):
        if len(value) != 1:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' must be a single value.",
                errors=[{"param": spec.name, "value": value}],
            )
        return InputDatasetProcessed(value=stringify(value[0]))
    return InputDatasetProcessed(value=stringify(value))


# -- dispatch table (must come after function definitions) -------------------

_DISPATCH_TABLE: dict[str, _ParamHandler] = {
    "multi-pick-vocabulary": process_multi_pick,
    "single-pick-vocabulary": process_single_pick,
    "filter": process_filter,
    "input-dataset": process_input_dataset,
    **dict.fromkeys(SCALAR_TYPES, process_scalar),
    **dict.fromkeys(RANGE_TYPES, process_range),
}
