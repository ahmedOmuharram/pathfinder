"""Shared validation and coercion helpers for parameter processing.

Used by both ``ParameterNormalizer`` (wire-safe WDK values) and
``ParameterCanonicalizer`` (API-friendly canonical shapes).

The shared dispatch chain lives in ``ParameterValueMixin._process_value``.
Each consumer (normalizer / canonicalizer) calls it and then applies its
own output formatting to the returned ``ProcessedParam``.
"""

from dataclasses import dataclass
from enum import Enum, auto

from veupath_chatbot.domain.parameters._decode_values import decode_values
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized, _safe_float
from veupath_chatbot.domain.parameters.vocab_utils import match_vocab_value
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject, JSONValue

# Param types that support numeric range constraints
_NUMERIC_PARAM_TYPES = frozenset({"number", "number-range"})

# ---------------------------------------------------------------------------
# Intermediate result of the shared dispatch chain
# ---------------------------------------------------------------------------


class ParamKind(Enum):
    """Discriminator for the ``ProcessedParam`` tagged union."""

    MULTI_PICK = auto()
    SINGLE_PICK = auto()
    SCALAR = auto()
    RANGE = auto()
    FILTER = auto()
    INPUT_DATASET = auto()
    UNKNOWN = auto()
    EMPTY = auto()


@dataclass(frozen=True)
class ProcessedParam:
    """Intermediate result from the shared dispatch chain.

    ``kind`` tells callers *what* was produced so they can apply output
    formatting (e.g. ``json.dumps`` for the wire normalizer, identity for the
    canonical API formatter).

    ``value`` holds the decoded, validated, native-Python value:
      - MULTI_PICK   -> ``list[str]``
      - SINGLE_PICK  -> ``str``
      - SCALAR       -> ``str``
      - RANGE        -> ``dict`` with ``min``/``max`` keys
      - FILTER       -> ``dict | list | str``
      - INPUT_DATASET -> ``str``
      - UNKNOWN      -> original ``JSONValue`` (pass-through)
      - EMPTY        -> ``""``
    """

    kind: ParamKind
    value: JSONValue


# Param-type groupings (avoids duplicating string literals)
SCALAR_TYPES = frozenset({"number", "date", "timestamp", "string"})
RANGE_TYPES = frozenset({"number-range", "date-range"})


class ParameterValueMixin:
    """Shared helpers for ``ParameterNormalizer`` and ``ParameterCanonicalizer``."""

    # -- public helpers used by both classes ----------------------------------

    def _stringify(self, value: JSONValue) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _handle_empty(self, spec: ParamSpecNormalized, value: JSONValue) -> JSONValue:
        if spec.allow_empty_value:
            return ""
        if spec.param_type in {"multi-pick-vocabulary", "single-pick-vocabulary"}:
            self._validate_single_required(spec)
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{spec.name}' requires a value.",
            errors=[{"param": spec.name}],
        )

    def _validate_multi_count(
        self, spec: ParamSpecNormalized, values: list[str]
    ) -> None:
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

    def _validate_single_required(self, spec: ParamSpecNormalized) -> None:
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

    def _validate_numeric_range(
        self, spec: ParamSpecNormalized, numeric_value: float
    ) -> None:
        """Validate a numeric value against min/max constraints if present."""
        if spec.min_value is not None and numeric_value < spec.min_value:
            raise ValidationError(
                title="Invalid parameter value",
                detail=(
                    f"Parameter '{spec.name}' value {numeric_value} "
                    f"is below minimum {spec.min_value}."
                ),
                errors=[{"param": spec.name, "value": numeric_value}],
            )
        if spec.max_value is not None and numeric_value > spec.max_value:
            raise ValidationError(
                title="Invalid parameter value",
                detail=(
                    f"Parameter '{spec.name}' value {numeric_value} "
                    f"exceeds maximum {spec.max_value}."
                ),
                errors=[{"param": spec.name, "value": numeric_value}],
            )

    def _validate_string_length(
        self, spec: ParamSpecNormalized, string_value: str
    ) -> None:
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

    def _try_parse_float(self, value: JSONValue) -> float | None:
        """Attempt to parse a value as float, returning None on failure."""
        return _safe_float(value)

    # -- shared dispatch chain ------------------------------------------------

    def _process_value(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> ProcessedParam:
        """Validate, decode, and coerce *value* according to *spec*.

        Returns a ``ProcessedParam`` whose ``kind`` tells the caller what
        output formatting to apply.  All validation errors are raised here
        so downstream formatters need not re-check.
        """
        if value is None:
            empty = self._handle_empty(spec, value)
            return ProcessedParam(kind=ParamKind.EMPTY, value=empty)

        param_type = spec.param_type

        if param_type == "multi-pick-vocabulary":
            return self._process_multi_pick(spec, value)

        if param_type == "single-pick-vocabulary":
            return self._process_single_pick(spec, value)

        if param_type in SCALAR_TYPES:
            return self._process_scalar(spec, value)

        if param_type in RANGE_TYPES:
            return self._process_range(spec, value)

        if param_type == "filter":
            return self._process_filter(value)

        if param_type == "input-dataset":
            return self._process_input_dataset(spec, value)

        return ProcessedParam(kind=ParamKind.UNKNOWN, value=value)

    # -- per-type processors (private) ----------------------------------------

    def _process_multi_pick(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> ProcessedParam:
        values = [self._stringify(v) for v in decode_values(value, spec.name)]
        matched: list[str] = [
            match_vocab_value(vocab=spec.vocabulary, param_name=spec.name, value=v)
            for v in values
        ]
        self._validate_multi_count(spec, matched)
        result_values: list[JSONValue] = list(matched)
        return ProcessedParam(kind=ParamKind.MULTI_PICK, value=result_values)

    def _process_single_pick(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> ProcessedParam:
        decoded = decode_values(value, spec.name)
        if len(decoded) > 1:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' allows only one value.",
                errors=[{"param": spec.name, "value": value}],
            )
        selected = self._stringify(decoded[0]) if decoded else ""
        if not selected:
            self._validate_single_required(spec)
            return ProcessedParam(kind=ParamKind.SINGLE_PICK, value="")
        selected = match_vocab_value(
            vocab=spec.vocabulary, param_name=spec.name, value=selected
        )
        if not selected:
            self._validate_single_required(spec)
        return ProcessedParam(
            kind=ParamKind.SINGLE_PICK, value=self._stringify(selected)
        )

    def _process_scalar(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> ProcessedParam:
        if isinstance(value, (list, dict, tuple, set)):
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' must be a scalar value.",
                errors=[{"param": spec.name, "value": value}],
            )
        str_value = self._stringify(value)

        # Numeric range constraint validation
        # Applies to NumberParam types AND StringParam with isNumber=true
        if spec.param_type in _NUMERIC_PARAM_TYPES or spec.is_number:
            parsed = self._try_parse_float(value)
            if parsed is not None:
                self._validate_numeric_range(spec, parsed)

        # String length constraint validation (only for string-type params)
        if spec.param_type == "string" and spec.max_length is not None:
            self._validate_string_length(spec, str_value)

        return ProcessedParam(kind=ParamKind.SCALAR, value=str_value)

    def _process_range(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> ProcessedParam:
        range_dict: JSONObject
        if isinstance(value, dict):
            range_dict = value
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            range_dict = {"min": value[0], "max": value[1]}
        else:
            raise ValidationError(
                title="Invalid parameter value",
                detail=f"Parameter '{spec.name}' must be a range.",
                errors=[{"param": spec.name, "value": value}],
            )

        # Validate each endpoint of the range against numeric constraints
        if spec.param_type in _NUMERIC_PARAM_TYPES:
            for key in ("min", "max"):
                endpoint = range_dict.get(key)
                if endpoint is not None:
                    parsed = self._try_parse_float(endpoint)
                    if parsed is not None:
                        self._validate_numeric_range(spec, parsed)

        return ProcessedParam(kind=ParamKind.RANGE, value=range_dict)

    def _process_filter(self, value: JSONValue) -> ProcessedParam:
        if isinstance(value, (dict, list)):
            return ProcessedParam(kind=ParamKind.FILTER, value=value)
        return ProcessedParam(kind=ParamKind.FILTER, value=self._stringify(value))

    def _process_input_dataset(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> ProcessedParam:
        if isinstance(value, list):
            if len(value) != 1:
                raise ValidationError(
                    title="Invalid parameter value",
                    detail=f"Parameter '{spec.name}' must be a single value.",
                    errors=[{"param": spec.name, "value": value}],
                )
            return ProcessedParam(
                kind=ParamKind.INPUT_DATASET, value=self._stringify(value[0])
            )
        return ProcessedParam(
            kind=ParamKind.INPUT_DATASET, value=self._stringify(value)
        )
