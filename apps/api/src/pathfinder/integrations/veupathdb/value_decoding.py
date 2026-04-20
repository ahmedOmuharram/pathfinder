"""WDK parameter value encoding/decoding.

WDK wire format is ``dict[str, str]`` (``SearchConfig.parameters`` with
``ParameterValue = string``). Scalars are bare strings; lists are JSON-encoded
strings; comma-separated values are accepted as CSV for multi-pick.

This module owns that wire knowledge. Domain types hold decoded values
(``DecodedParams = dict[str, JsonValue]``); encoding to ``WireParams``
happens at integration boundaries only.
"""

import csv
import json
from typing import cast

import json5
from pydantic import JsonValue

from pathfinder.domain.strategy.types import DecodedParams, WireParams
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


def decode_values(value: JsonValue, name: str) -> list[JsonValue]:
    """Coerce a param value (scalar or WDK-encoded string) into a list."""
    if value is None:
        return []
    if isinstance(value, dict):
        raise ValidationError(
            title="Invalid parameter value",
            detail=f"Parameter '{name}' does not accept dictionaries.",
            errors=[{"param": name, "value": value}],
        )
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v is not None]
    if isinstance(value, str):
        return _decode_string_value(value)
    return [value]


def _decode_string_value(value: str) -> list[JsonValue]:
    stripped = value.strip()
    if not stripped:
        return []
    parsed = parse_json5_value(stripped)
    if isinstance(parsed, list):
        return [v for v in parsed if v is not None]
    if parsed is not None:
        return [parsed]
    if "," in stripped:
        row = next(csv.reader([stripped], skipinitialspace=True))
        return [item for item in row if item is not None and str(item).strip()]
    return [stripped]


def parse_json5_value(raw: str) -> JsonValue | None:
    try:
        result = json5.loads(raw)
        return cast("JsonValue", result)
    except (ValueError, TypeError) as exc:
        logger.debug("Failed to parse JSON5 value", error=str(exc))
        return None


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
