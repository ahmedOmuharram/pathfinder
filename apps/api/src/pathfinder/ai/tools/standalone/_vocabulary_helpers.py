"""Vocabulary matching and search filtering helpers.

Functions for matching user-provided values against WDK parameter
vocabularies, extracting display options from vocabulary trees,
filtering search lists, and expanding leaf values.
"""

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pathfinder.domain.parameters.vocab_utils import (
    BROAD_VALUE_FIELDS,
    collect_leaf_terms,
    find_vocab_node,
    flatten_vocab,
    get_node_value,
    normalize_vocab_key,
)
from pathfinder.platform.types import JSONArray, JSONObject

# ---------------------------------------------------------------------------
# Private parsing models (replace isinstance/dict.get chains per CLAUDE.md)
# ---------------------------------------------------------------------------

class _SearchEntry(BaseModel):
    """Parse a WDK search entry from the JSON API."""

    model_config = ConfigDict(extra="ignore")
    name: str = ""
    url_segment: str = Field(default="")
    display_name: str = Field(default="")

class _VocabNodeData(BaseModel):
    """The ``data`` sub-object of a WDK vocabulary tree node."""

    model_config = ConfigDict(extra="ignore")
    display: str | None = None

class _VocabNode(BaseModel):
    """A single node in a WDK vocabulary tree."""

    model_config = ConfigDict(extra="ignore")
    data: _VocabNodeData = Field(default_factory=_VocabNodeData)
    children: list["_VocabNode"] = Field(default_factory=list)

class _VocabEntry(BaseModel):
    """A flattened vocabulary entry (output of ``flatten_vocab``)."""

    model_config = ConfigDict(extra="ignore")
    display: str | None = None
    value: str | None = None

# ---------------------------------------------------------------------------
# Search filtering
# ---------------------------------------------------------------------------

def filter_search_options(
    searches: JSONArray, query: str, limit: int = 20
) -> list[str]:
    lowered = query.lower()
    results: list[str] = []
    for raw in searches:
        entry = _SearchEntry.model_validate(raw)
        name = entry.name or entry.url_segment
        display = entry.display_name
        if lowered in name.lower() or lowered in display.lower():
            result_value = name or display
            if result_value:
                results.append(result_value)
        if len(results) >= limit:
            break
    return results

# ---------------------------------------------------------------------------
# Vocabulary extraction and matching
# ---------------------------------------------------------------------------

def extract_vocab_options(
    vocabulary: JSONObject, limit: int = 50
) -> list[str]:
    options: list[str] = []

    def walk(node: _VocabNode) -> None:
        if len(options) >= limit:
            return
        display = node.data.display
        if display and display != "@@fake@@":
            options.append(display)
        for child in node.children:
            walk(child)

    if vocabulary:
        walk(_VocabNode.model_validate(vocabulary))
    return options

def match_vocab_value(
    vocabulary: JSONObject | JSONArray, value: JsonValue
) -> str:
    target = "" if value is None else str(value)
    if not target or not vocabulary:
        return target
    entries = flatten_vocab(vocabulary, prefer_term=False)
    exact = match_vocab_exact(entries, target)
    return (
        exact
        if exact is not None
        else match_vocab_normalized(entries, target)
    )

def match_vocab_exact(
    entries: list[dict[str, str | None]], target: str
) -> str | None:
    """Return the vocab value for an exact match against display or value."""
    for raw in entries:
        entry = _VocabEntry.model_validate(raw)
        if target == entry.display:
            return entry.value or entry.display or target
        if target == entry.value:
            return entry.value or target
    return None

def match_vocab_normalized(
    entries: list[dict[str, str | None]], target: str
) -> str:
    """Return the vocab value for a normalized match, or target if no match."""
    normalized_target = normalize_vocab_key(target)
    for raw in entries:
        entry = _VocabEntry.model_validate(raw)
        if entry.display and normalize_vocab_key(entry.display) == normalized_target:
            return entry.value or entry.display
        if entry.value and normalize_vocab_key(entry.value) == normalized_target:
            return entry.value
    return target

def expand_leaf_values(
    vocabulary: JSONObject,
    values: list[str],
    *,
    include_parent: bool = False,
) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for value in values:
        match = str(value)
        if not match:
            continue
        node = find_vocab_node(
            vocabulary, match, fields=BROAD_VALUE_FIELDS, normalize=True
        )
        if not node:
            if match not in seen:
                seen.add(match)
                expanded.append(match)
            continue
        if include_parent:
            parent_value = get_node_value(node, fields=BROAD_VALUE_FIELDS) or ""
            if parent_value and parent_value not in seen:
                seen.add(parent_value)
                expanded.append(parent_value)
        for leaf in collect_leaf_terms(node, fields=BROAD_VALUE_FIELDS):
            if leaf and leaf not in seen:
                seen.add(leaf)
                expanded.append(leaf)
    return expanded
