"""Shared WDK parameter value normalization.

WDK expects all parameter values as strings. Multi-pick enum params use a
JSON array string (see ``AbstractEnumParam.getExternalStableValue`` in the
WDK source). Single-pick params use a plain string value.
"""

from __future__ import annotations

import json

from veupath_chatbot.platform.types import JSONValue


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
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)
