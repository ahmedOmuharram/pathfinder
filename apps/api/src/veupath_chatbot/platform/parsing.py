"""Parsing helpers shared across layers."""

from __future__ import annotations

import json


def parse_jsonish(value: str | dict | list | None) -> dict | list | None:
    """Parse tool results that may be JSON or a Python literal.

    Some tool frameworks return `dict`/`list`, others return a string (often JSON),
    and some return a Python-literal string representation. This function handles
    those cases without making assumptions about the payload schema.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        try:
            import ast

            parsed = ast.literal_eval(value)
        except Exception:
            return None
        return parsed if isinstance(parsed, (dict, list)) else None

