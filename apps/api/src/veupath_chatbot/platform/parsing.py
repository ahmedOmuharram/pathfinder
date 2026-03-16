"""Parsing helpers shared across layers."""

import json

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject

logger = get_logger(__name__)


def parse_jsonish(
    value: str | JSONObject | JSONArray | None,
) -> JSONObject | JSONArray | None:
    """Parse tool results that may be JSON or a Python literal.

    Some tool frameworks return `dict`/`list`, others return a string (often JSON),
    and some return a Python-literal string representation. This function handles
    those cases without making assumptions about the payload schema.

    :param value: str | JSONObject | JSONArray | None.

    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed_json = json.loads(value)
        if isinstance(parsed_json, (dict, list)):
            return parsed_json
        return None
    except json.JSONDecodeError:
        try:
            import ast

            parsed = ast.literal_eval(value)
        except Exception as exc:
            logger.debug("Failed to parse value as Python literal", error=str(exc))
            return None
        return parsed if isinstance(parsed, (dict, list)) else None
