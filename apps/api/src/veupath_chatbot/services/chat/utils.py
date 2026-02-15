"""Small chat utilities (parsing, ids)."""

from __future__ import annotations

import json
import re
from uuid import UUID

from veupath_chatbot.platform.types import JSONObject


def parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def parse_selected_nodes(message: str) -> tuple[JSONObject | None, str]:
    """Parse the `__NODE__{json}\\n<text>` prefix used by the UI.

    :param message: Chat message.

    """
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


_ORDERED_MARKER_RE = re.compile(r"^(\s*)(\d+)\.\s*$")
_BULLET_MARKER_RE = re.compile(r"^(\s*)([-*+])\s*$")


def sanitize_markdown(message: str) -> str:
    """Fix common markdown rendering issues from LLM output.

    Primary fix: avoid "bare list marker" lines like:

      1.

      Title:

    Which render as an empty list item. We merge the marker with the next
    non-empty line:

      1. Title:

    :param message: Chat message.

    """
    if not message or "\n" not in message:
        return message

    lines = message.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m_ord = _ORDERED_MARKER_RE.match(line)
        m_bul = _BULLET_MARKER_RE.match(line)
        if not (m_ord or m_bul):
            i += 1
            continue

        # Find next non-empty line to merge.
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            i += 1
            continue

        next_line = lines[j].lstrip()
        if m_ord:
            indent, num = m_ord.group(1), m_ord.group(2)
            lines[i] = f"{indent}{num}. {next_line}"
        elif m_bul:
            indent, bullet = m_bul.group(1), m_bul.group(2)
            lines[i] = f"{indent}{bullet} {next_line}"

        # Remove consumed blank lines + merged content line.
        del lines[i + 1 : j + 1]
        i += 1

    return "\n".join(lines).strip()
