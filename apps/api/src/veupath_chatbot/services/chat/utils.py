"""Small chat utilities (parsing, ids)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID


def parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def parse_selected_nodes(message: str) -> tuple[dict[str, Any] | None, str]:
    """Parse the `__NODE__{json}\\n<text>` prefix used by the UI."""
    if not message.startswith("__NODE__"):
        return None, message
    raw = message[len("__NODE__") :]
    newline_index = raw.find("\n")
    json_part = raw if newline_index == -1 else raw[:newline_index]
    text_part = "" if newline_index == -1 else raw[newline_index + 1 :]
    try:
        selected = json.loads(json_part.strip())
    except json.JSONDecodeError:
        return None, message
    return selected, text_part.strip()

