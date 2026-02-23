"""Safe accessors for untyped JSON structures.

These helpers reduce the ``isinstance`` / ``.get()`` boilerplate that
dominates code working with raw WDK responses.
"""

from __future__ import annotations

from veupath_chatbot.platform.types import JSONObject, JSONValue


def safe_str(obj: JSONValue, key: str, default: str = "") -> str:
    """Extract a string value from a JSON object.

    :param obj: Raw JSON value (expected to be a dict).
    :param key: Key to look up.
    :param default: Fallback when key is missing or value is not a string.
    """
    if not isinstance(obj, dict):
        return default
    value = obj.get(key)
    return value if isinstance(value, str) else default


def safe_int(obj: JSONValue, key: str, default: int | None = None) -> int | None:
    """Extract an integer value from a JSON object.

    :param obj: Raw JSON value (expected to be a dict).
    :param key: Key to look up.
    :param default: Fallback when key is missing or value is not an int.
    """
    if not isinstance(obj, dict):
        return default
    value = obj.get(key)
    return value if isinstance(value, int) else default


def safe_bool(obj: JSONValue, key: str, default: bool | None = None) -> bool | None:
    """Extract a boolean value from a JSON object.

    :param obj: Raw JSON value (expected to be a dict).
    :param key: Key to look up.
    :param default: Fallback when key is missing or value is not a bool.
    """
    if not isinstance(obj, dict):
        return default
    value = obj.get(key)
    return bool(value) if isinstance(value, bool) else default


def safe_dict(obj: JSONValue, key: str) -> JSONObject:
    """Extract a dict value from a JSON object, returning ``{}`` if absent.

    :param obj: Raw JSON value (expected to be a dict).
    :param key: Key to look up.
    """
    if not isinstance(obj, dict):
        return {}
    value = obj.get(key)
    return value if isinstance(value, dict) else {}


def safe_list(obj: JSONValue, key: str) -> list[JSONValue]:
    """Extract a list value from a JSON object, returning ``[]`` if absent.

    :param obj: Raw JSON value (expected to be a dict).
    :param key: Key to look up.
    """
    if not isinstance(obj, dict):
        return []
    value = obj.get(key)
    return value if isinstance(value, list) else []


def ensure_dict(obj: JSONValue) -> JSONObject:
    """Narrow a JSON value to a dict, returning ``{}`` if it is not one.

    :param obj: Raw JSON value.
    """
    return obj if isinstance(obj, dict) else {}


def iter_dicts(items: JSONValue) -> list[JSONObject]:
    """Filter a JSON array to only dict entries.

    :param items: Raw JSON value (expected to be a list).
    :returns: List of dict items, skipping non-dict entries.
    """
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def safe_name(obj: JSONValue, default: str = "") -> str:
    """Extract canonical name (urlSegment or name) from a WDK entity dict.

    :param obj: Raw JSON value (expected to be a dict).
    :param default: Fallback when both keys are missing or not strings.
    """
    return safe_str(obj, "urlSegment") or safe_str(obj, "name") or default
