"""Shared WDK parameter value normalization and JSON shape helpers.

WDK expects all parameter values as strings. Multi-pick enum params use a
JSON array string (see ``AbstractEnumParam.getExternalStableValue`` in the
WDK source). Single-pick params use a plain string value.

Also provides small helpers for extracting canonical names from WDK entity
dicts (record types, searches) so callers don't repeat the
``urlSegment || name`` pattern.
"""

import json

from veupath_chatbot.platform.types import JSONObject, JSONValue


def normalize_param_value(value: JSONValue) -> str:
    """Convert a JSON parameter value to the string format WDK expects.

    :param value: Raw parameter value (str, int, float, bool, list, dict, or None).
    :returns: WDK-compatible string representation.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        result = str(value)
    elif isinstance(value, (list, dict)):
        result = json.dumps(value)
    else:
        result = str(value)
    return result


def wdk_entity_name(obj: JSONObject | JSONValue) -> str:
    """Extract the canonical name from a WDK entity dict.

    WDK record-type and search objects expose ``urlSegment`` (preferred)
    and ``name`` as identifiers. This helper returns whichever is
    available, preferring ``urlSegment``.

    :param obj: WDK entity dict (record type or search).
    :returns: Canonical name string, or "" if neither field exists.
    """
    if isinstance(obj, str):
        return obj
    if not isinstance(obj, dict):
        return ""
    url_seg_raw = obj.get("urlSegment")
    name_raw = obj.get("name")
    url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
    name = name_raw if isinstance(name_raw, str) else None
    return url_seg or name or ""


def wdk_search_matches(search: JSONValue, search_name: str) -> bool:
    """Check whether a WDK search dict matches a given search name.

    :param search: WDK search dict.
    :param search_name: Search name to match against.
    :returns: True if ``urlSegment`` or ``name`` equals *search_name*.
    """
    if not isinstance(search, dict):
        return False
    url_seg_raw = search.get("urlSegment")
    name_raw = search.get("name")
    url_seg = url_seg_raw if isinstance(url_seg_raw, str) else None
    name = name_raw if isinstance(name_raw, str) else None
    return search_name in (url_seg, name)
