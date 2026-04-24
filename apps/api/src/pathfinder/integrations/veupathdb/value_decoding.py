"""WDK parameter value encoding/decoding.

WDK wire format is ``dict[str, str]`` (``SearchConfig.parameters`` with
``ParameterValue = string``). Scalars are bare strings; lists are JSON-encoded
strings; comma-separated values are accepted as CSV for multi-pick.

This module owns the WDK wire knowledge. Pure value-shape primitives
(``decode_values``, ``parse_json5_value``) live in
``pathfinder.domain.parameters.value_utils`` and are re-used here.
"""

import json

from pydantic import JsonValue

from pathfinder.domain.parameters.value_utils import parse_json5_value
from pathfinder.domain.strategy.types import DecodedParams, WireParams


def decode_param_value(raw: str) -> JsonValue:
    """Decode a single WDK wire value into a JSON-typed value.

    Tries JSON5 parse first (handles lists, numbers, booleans, null,
    JSON-quoted strings). Falls back to the raw string.
    """
    stripped = raw.strip()
    if not stripped:
        return ""
    parsed = parse_json5_value(stripped)
    if parsed is None:
        return raw
    return parsed


def decode_params(wire: WireParams) -> DecodedParams:
    """Decode each WDK wire value into its natural JSON type."""
    return {name: decode_param_value(value) for name, value in wire.items()}


def _encode_value(value: JsonValue) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def encode_params(decoded: DecodedParams) -> WireParams:
    """Encode decoded params back into WDK wire format (``dict[str, str]``)."""
    return {name: _encode_value(value) for name, value in decoded.items()}
