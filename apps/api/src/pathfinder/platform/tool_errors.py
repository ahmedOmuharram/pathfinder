"""Helpers for standardized AI tool error payloads.

:func:`tool_error` returns a :class:`ToolErrorPayload` model directly.
Kani natively calls ``.model_dump_json()`` on BaseModel returns from
``@ai_function`` methods, so returning a model is zero-behavior-change
for the LLM while preserving type safety for Python callers.
"""

from enum import Enum

from pydantic import JsonValue

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class ToolErrorPayload(CamelModel):
    """Complete tool-error wrapper validated at construction time."""

    ok: bool = False
    code: str
    message: str
    details: JSONObject | None = None


def tool_error(
    code: str | Enum, message: str, **details: JsonValue
) -> ToolErrorPayload:
    """Build a standardized tool error payload.

    :param code: Error code (string or Enum).
    :param message: Error message.
    :param details: Additional details as keyword arguments.
    :returns: Validated :class:`ToolErrorPayload` model.
    """
    code_value = code.value if isinstance(code, Enum) else str(code)
    details_obj: JSONObject | None = {**details} if details else None
    return ToolErrorPayload(
        code=code_value,
        message=message,
        details=details_obj,
    )
