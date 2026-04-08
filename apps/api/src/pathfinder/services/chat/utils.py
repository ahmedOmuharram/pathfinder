"""Small chat utilities (parsing, ids)."""

import json

from pathfinder.platform.types import JSONObject


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
