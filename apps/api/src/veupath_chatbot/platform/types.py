"""Common type aliases for the codebase."""

from __future__ import annotations

from pydantic import JsonValue

# JSON types: Python's standard representation for JSON objects/arrays
# JSON keys are always strings, values can be any JSON-serializable type
type JSONValue = JsonValue
"""Type alias for JSON values."""

type JSONObject = dict[str, JSONValue]
"""Type alias for JSON objects (dictionaries with string keys)."""

type JSONArray = list[JSONValue]
"""Type alias for JSON arrays."""


def as_json_object(value: JSONValue) -> JSONObject:
    """Type guard: assert that a JSONValue is a JSONObject."""
    if not isinstance(value, dict):
        raise TypeError(f"Expected dict, got {type(value)}")
    # After isinstance check, value is known to be dict[str, JSONValue]
    return value


def as_json_array(value: JSONValue) -> JSONArray:
    """Type guard: assert that a JSONValue is a JSONArray."""
    if not isinstance(value, list):
        raise TypeError(f"Expected list, got {type(value)}")
    # After isinstance check, value is known to be list[JSONValue]
    return value
