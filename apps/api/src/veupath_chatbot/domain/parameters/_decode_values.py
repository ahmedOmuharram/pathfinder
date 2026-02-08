"""Shared helpers for decoding parameter values."""

from __future__ import annotations

import csv
from typing import cast

import json5

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONValue


def decode_values(value: JSONValue, name: str) -> list[JSONValue]:
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
    return [value]


def parse_json5_value(raw: str) -> JSONValue | None:
    try:
        # json5.loads returns Any, but we know it's JSON-serializable
        result = json5.loads(raw)
        return cast(JSONValue, result)
    except Exception:
        return None
