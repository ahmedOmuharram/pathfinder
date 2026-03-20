"""Vocabulary tree rendering and value extraction.

Pure module (no I/O). Formats WDK vocabulary trees for display and
extracts allowed parameter values from vocabulary data.
"""

from veupath_chatbot.domain.parameters.vocab_utils import (
    flatten_vocab,
    get_node_term,
    get_vocab_children,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject

# Cap rendered vocab entries so the LLM tool response stays within a
# manageable size; large WDK vocabularies can have thousands of values.
_MAX_VOCAB_ENTRIES = 50


def render_vocab_tree(
    node: JSONObject,
    *,
    max_lines: int = 80,
    _depth: int = 0,
    _lines: list[str] | None = None,
) -> list[str]:
    """Render a WDK tree vocabulary as indented text lines.

    Each line is ``"  " * depth + term``.  Stops after *max_lines* to avoid
    blowing up the tool response for huge trees.
    """
    if _lines is None:
        _lines = []
    if len(_lines) >= max_lines:
        return _lines

    term = get_node_term(node)
    if term and term != "@@fake@@":
        _lines.append(f"{'  ' * _depth}{term}")

    for child in get_vocab_children(node):
        if len(_lines) >= max_lines:
            _lines.append("  ... (truncated)")
            break
        render_vocab_tree(child, max_lines=max_lines, _depth=_depth + 1, _lines=_lines)

    return _lines


def allowed_values(
    vocab: JSONObject | JSONArray | None,
) -> list[JSONObject]:
    """Extract WDK-accepted parameter values from a vocabulary.

    Returns ``[{"value": <wdk_value>, "display": <label>}, ...]`` so the LLM
    knows both *what to pass* and *what it means*.

    :param vocab: Vocabulary tree or flat list from catalog.
    :returns: List of value/display dicts (capped at 50).
    """
    if not vocab:
        return []
    entries: list[JSONObject] = []
    seen: set[str] = set()
    for entry in flatten_vocab(vocab, prefer_term=True):
        # Prefer the WDK-accepted value; fall back to display if missing.
        candidate = entry.get("value") or entry.get("display")
        if not candidate:
            continue
        text = str(candidate)
        if text in seen:
            continue
        seen.add(text)
        display = entry.get("display")
        display_str = str(display) if display else text
        entries.append({"value": text, "display": display_str})
        if len(entries) >= _MAX_VOCAB_ENTRIES:
            break
    return entries
