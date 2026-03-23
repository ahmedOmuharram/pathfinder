"""Helpers for standardized AI tool error payloads.

Uses :class:`ToolErrorPayload` internally for shape validation, but returns
a plain ``JSONObject`` for kani compatibility (kani serializes tool returns
with ``json.dumps``).
"""

from enum import Enum

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue


class ToolErrorPayload(CamelModel):
    """Complete tool-error wrapper validated at construction time.

    The model validates shape; callers receive a plain dict via
    :func:`tool_error` for kani JSON-serialization compatibility.
    """

    ok: bool = False
    code: str
    message: str
    details: JSONObject | None = None


def tool_error(code: str | Enum, message: str, **details: JSONValue) -> JSONObject:
    """Build a standardized tool error payload.

    Validates shape via :class:`ToolErrorPayload`, serializes with
    ``model_dump``, then flat-promotes detail keys so the AI agent sees
    them at the top level (kani serializes tool returns with ``json.dumps``).

    :param code: Error code (string or Enum).
    :param message: Error message.
    :param details: Additional details as keyword arguments.
    :returns: Standardized error payload dict.
    """
    code_value = code.value if isinstance(code, Enum) else str(code)
    details_obj: JSONObject | None = dict(details) if details else None
    payload = ToolErrorPayload(
        code=code_value, message=message, details=details_obj,
    ).model_dump(by_alias=True, exclude_none=True, mode="json")
    # Flat-promote detail keys so the AI agent sees them at the top level.
    if details:
        for key, value in details.items():
            if key not in payload and value is not None:
                payload[key] = value
    return payload
