"""Normalize parameter values into WDK wire format.

Delegates validation and decoding to the shared dispatch chain in
``_value_helpers.process_value()``, then applies WDK wire formatting:
compound types (multi-pick lists, ranges, filter dicts/lists) are
serialized as JSON strings.
"""

import json
from dataclasses import dataclass

from veupath_chatbot.domain.parameters._value_helpers import (
    ParamKind,
    process_value,
)
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import (
    JSONObject,
    JSONValue,
)

# WDK wire format wraps these compound kinds with json.dumps().
_WIRE_JSON_KINDS = frozenset({ParamKind.MULTI_PICK, ParamKind.RANGE, ParamKind.FILTER})


@dataclass(frozen=True)
class ParameterNormalizer:
    """Normalize parameter values using canonical parameter specs.

    Produces WDK wire-safe values: multi-pick lists become JSON strings,
    ranges become JSON strings, filters become JSON strings.
    Does NOT expand selections to leaf terms -- even when WDK marks a
    vocabulary as ``countOnlyLeaves``, WDK handles that expansion itself.
    """

    specs: dict[str, ParamSpecNormalized]

    def normalize(self, parameters: JSONObject) -> JSONObject:
        normalized: JSONObject = {}
        for name, value in (parameters or {}).items():
            spec = self.specs.get(name)
            if not spec:
                available = sorted(self.specs.keys())
                raise ValidationError(
                    title="Unknown parameter",
                    detail=f"Parameter '{name}' does not exist for this search. Available parameters: {', '.join(available)}",
                    errors=[{"param": name, "value": value}],
                )
            if spec.param_type == "input-step":
                continue
            normalized[name] = self._normalize_value(spec, value)
        return normalized

    def _normalize_value(
        self, spec: ParamSpecNormalized, value: JSONValue
    ) -> JSONValue:
        result = process_value(spec, value)

        # WDK wire format: compound types must be serialized as JSON strings.
        if result.kind in _WIRE_JSON_KINDS and isinstance(result.value, (list, dict)):
            return json.dumps(result.value)

        return result.value
