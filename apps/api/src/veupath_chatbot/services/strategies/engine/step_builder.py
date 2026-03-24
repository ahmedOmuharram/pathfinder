"""Step creation, parameter assembly, and vocabulary helpers."""

from veupath_chatbot.domain.parameters.vocab_utils import (
    BROAD_VALUE_FIELDS,
    collect_leaf_terms,
    find_vocab_node,
    flatten_vocab,
    get_node_value,
    normalize_vocab_key,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue

from .base import StrategyToolsBase


class StepBuilderMixin(StrategyToolsBase):
    def _filter_search_options(
        self, searches: JSONArray, query: str, limit: int = 20
    ) -> list[str]:
        lowered = query.lower()
        results: list[str] = []
        for search in searches:
            if not isinstance(search, dict):
                continue
            name_raw = search.get("name") or search.get("urlSegment")
            name = name_raw if isinstance(name_raw, str) else ""
            display_raw = search.get("displayName")
            display = display_raw if isinstance(display_raw, str) else ""
            name_lower = name.lower() if isinstance(name, str) else ""
            display_lower = display.lower() if isinstance(display, str) else ""
            if lowered in name_lower or lowered in display_lower:
                result_value = name or display
                if result_value:
                    results.append(result_value)
            if len(results) >= limit:
                break
        return results

    def _extract_vocab_options(
        self, vocabulary: JSONObject, limit: int = 50
    ) -> list[str]:
        options: list[str] = []

        def walk(node: JSONObject) -> None:
            if len(options) >= limit:
                return
            data_raw = node.get("data")
            data = data_raw if isinstance(data_raw, dict) else {}
            display_raw = data.get("display")
            display = display_raw if isinstance(display_raw, str) else None
            if display and display != "@@fake@@":
                options.append(display)
            children_raw = node.get("children")
            children = children_raw if isinstance(children_raw, list) else []
            for child in children:
                if isinstance(child, dict):
                    walk(child)

        if vocabulary:
            walk(vocabulary)
        return options

    def _match_vocab_value(
        self, vocabulary: JSONObject | JSONArray, value: JSONValue
    ) -> str:
        target = "" if value is None else str(value)
        if not target or not vocabulary:
            return target
        entries = flatten_vocab(vocabulary, prefer_term=False)
        exact = self._match_vocab_exact(entries, target)
        return (
            exact
            if exact is not None
            else self._match_vocab_normalized(entries, target)
        )

    def _match_vocab_exact(
        self, entries: list[dict[str, str | None]], target: str
    ) -> str | None:
        """Return the vocab value for an exact match against display or value."""
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if target == display:
                return raw_value or display or target
            if target == raw_value:
                return raw_value or target
        return None

    def _match_vocab_normalized(
        self, entries: list[dict[str, str | None]], target: str
    ) -> str:
        """Return the vocab value for a normalized match, or target if no match."""
        normalized_target = normalize_vocab_key(target)
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if display and normalize_vocab_key(display) == normalized_target:
                return raw_value or display
            if raw_value and normalize_vocab_key(raw_value) == normalized_target:
                return raw_value
        return target

    def _expand_leaf_values(
        self,
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
