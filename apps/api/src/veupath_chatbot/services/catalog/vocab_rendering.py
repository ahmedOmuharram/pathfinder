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


def _count_descendants(node: JSONObject) -> int:
    """Count all descendants of a vocab tree node (excluding itself)."""
    children = get_vocab_children(node)
    total = len(children)
    for child in children:
        total += _count_descendants(child)
    return total


def render_vocab_tree(
    node: JSONObject,
    *,
    max_lines: int = 80,
    _depth: int = 0,
    _lines: list[str] | None = None,
) -> list[str]:
    """Render a WDK tree vocabulary as indented text lines.

    Each line is ``"  " * depth + term``.  When the tree exceeds
    *max_lines*, top-level categories are always shown with descendant
    counts so the model knows what exists beyond the truncation point.
    """
    if _lines is None:
        _lines = []
    if len(_lines) >= max_lines:
        return _lines

    term = get_node_term(node)
    is_fake_root = term is None or term == "@@fake@@"

    if not is_fake_root:
        _lines.append(f"{'  ' * _depth}{term}")

    children = get_vocab_children(node)

    for child in children:
        if len(_lines) >= max_lines:
            # Show remaining top-level categories as summaries.
            remaining = children[children.index(child):]
            for r in remaining:
                r_term = get_node_term(r)
                if r_term and r_term != "@@fake@@":
                    desc_count = _count_descendants(r)
                    if desc_count > 0:
                        _lines.append(
                            f"{'  ' * (_depth + 1)}{r_term} ({desc_count} entries, "
                            f"use query='{r_term.split()[0].lower()}' to see)"
                        )
                    else:
                        _lines.append(f"{'  ' * (_depth + 1)}{r_term}")
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
