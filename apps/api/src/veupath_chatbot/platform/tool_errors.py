"""Helpers for standardized AI tool error payloads."""

from __future__ import annotations

from enum import Enum
from typing import Any


def tool_error(code: str | Enum, message: str, **details: Any) -> dict[str, Any]:
    """Build a standardized tool error payload."""
    code_value = code.value if isinstance(code, Enum) else str(code)
    payload: dict[str, Any] = {"ok": False, "code": code_value, "message": message}
    if details:
        payload["details"] = details
        for key, value in details.items():
            if key not in payload and value is not None:
                payload[key] = value
    return payload
