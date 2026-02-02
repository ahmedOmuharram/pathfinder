"""Shared helpers for decoding parameter values."""

from __future__ import annotations

import csv
from typing import Any

import json5

from veupath_chatbot.platform.errors import ValidationError


def decode_values(value: Any, name: str) -> list[Any]:
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


def parse_json5_value(raw: str) -> Any | None:
    try:
        return json5.loads(raw)
    except Exception:
        return None
