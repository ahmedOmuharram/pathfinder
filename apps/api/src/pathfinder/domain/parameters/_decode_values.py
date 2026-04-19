"""Shared helpers for decoding parameter values."""

import csv
from typing import cast

import json5
from pydantic import JsonValue

from pathfinder.platform.errors import ValidationError
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

def decode_values(value: JsonValue, name: str) -> list[JsonValue]:
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
        # json5.loads returns Any, but we know it's JSON-serializable
        result = json5.loads(raw)
        return cast("JsonValue", result)
    except (ValueError, TypeError) as exc:
        logger.debug("Failed to parse JSON5 value", error=str(exc))
        return None
