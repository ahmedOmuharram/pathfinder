"""Step creation, parameter assembly, and vocabulary helpers."""

from __future__ import annotations

from veupath_chatbot.domain.parameters.vocab_utils import (
    flatten_vocab,
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
        if value is None:
            return ""
        target = str(value)
        if not target or not vocabulary:
            return target
        entries = flatten_vocab(vocabulary, prefer_term=False)
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if target == display:
                return raw_value or display or target
            if target == raw_value:
                return raw_value or target
        normalized_target = normalize_vocab_key(target)
        for entry in entries:
            display = entry.get("display")
            raw_value = entry.get("value")
            if display and normalize_vocab_key(display) == normalized_target:
                return raw_value or display
            if raw_value and normalize_vocab_key(raw_value) == normalized_target:
                return raw_value
        return target

    def _vocab_contains_value(self, vocabulary: JSONObject, value: str) -> bool:
        """Check if a vocabulary tree contains the value (display or value field).

        :param vocabulary: Vocabulary tree from catalog.
        :param value: Value to search for.
        :returns: True if value is found.
        """
        target = value.strip()
        if not target or not vocabulary:
            return False

        def walk(node: JSONObject) -> bool:
            data_raw = node.get("data")
            data = data_raw if isinstance(data_raw, dict) else {}
            display_raw = data.get("display")
            display = display_raw if isinstance(display_raw, str) else None
            value_raw = data.get("value")
            raw_value = value_raw if isinstance(value_raw, str) else None
            if target in (display, raw_value):
                return True
            children_raw = node.get("children")
            children = children_raw if isinstance(children_raw, list) else []
            return any(isinstance(child, dict) and walk(child) for child in children)

        return walk(vocabulary)

    def _get_vocab_node_value(self, node: JSONObject) -> str:
        data_raw = node.get("data")
        data = data_raw if isinstance(data_raw, dict) else {}
        value_raw = data.get("value")
        id_raw = data.get("id")
        term_raw = data.get("term")
        name_raw = data.get("name")
        display_raw = data.get("display")
        raw_value: str | None = None
        if isinstance(value_raw, str):
            raw_value = value_raw
        elif isinstance(id_raw, str):
            raw_value = id_raw
        elif isinstance(term_raw, str):
            raw_value = term_raw
        elif isinstance(name_raw, str):
            raw_value = name_raw
        elif isinstance(display_raw, str):
            raw_value = display_raw
        return raw_value if raw_value is not None else ""

    def _find_vocab_node_for_match(
        self, node: JSONObject, match: str
    ) -> JSONObject | None:
        data_raw = node.get("data")
        data = data_raw if isinstance(data_raw, dict) else {}
        value_raw = data.get("value")
        id_raw = data.get("id")
        term_raw = data.get("term")
        name_raw = data.get("name")
        display_raw = data.get("display")
        candidates: list[JSONValue] = []
        if value_raw is not None:
            candidates.append(value_raw)
        if id_raw is not None:
            candidates.append(id_raw)
        if term_raw is not None:
            candidates.append(term_raw)
        if name_raw is not None:
            candidates.append(name_raw)
        if display_raw is not None:
            candidates.append(display_raw)
        for candidate in candidates:
            if match == str(candidate):
                return node
        normalized = normalize_vocab_key(match)
        for candidate in candidates:
            if normalize_vocab_key(str(candidate)) == normalized:
                return node
        children_raw = node.get("children")
        children = children_raw if isinstance(children_raw, list) else []
        for child in children:
            if isinstance(child, dict):
                found = self._find_vocab_node_for_match(child, match)
                if found:
                    return found
        return None

    def _collect_leaf_terms(self, node: JSONObject) -> list[str]:
        children_raw = node.get("children")
        children = children_raw if isinstance(children_raw, list) else []
        if not children:
            value = self._get_vocab_node_value(node)
            return [value] if value else []
        leaves: list[str] = []
        for child in children:
            if isinstance(child, dict):
                leaves.extend(self._collect_leaf_terms(child))
        return leaves

    def _expand_leaf_values(
        self,
        vocabulary: JSONObject,
        values: list[str],
        include_parent: bool = False,
    ) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for value in values:
            match = str(value)
            if not match:
                continue
            node = self._find_vocab_node_for_match(vocabulary, match)
            if not node:
                if match not in seen:
                    seen.add(match)
                    expanded.append(match)
                continue
            if include_parent:
                parent_value = self._get_vocab_node_value(node)
                if parent_value and parent_value not in seen:
                    seen.add(parent_value)
                    expanded.append(parent_value)
            for leaf in self._collect_leaf_terms(node):
                if leaf and leaf not in seen:
                    seen.add(leaf)
                    expanded.append(leaf)
        return expanded
