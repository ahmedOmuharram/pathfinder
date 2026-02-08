"""Vocabulary utilities."""

from __future__ import annotations

import re

from veupath_chatbot.platform.types import JSONArray, JSONObject


def normalize_vocab_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def flatten_vocab(
    vocabulary: JSONObject | JSONArray, prefer_term: bool = False
) -> list[dict[str, str | None]]:
    entries: list[dict[str, str | None]] = []

    def choose_value(data: JSONObject) -> str | None:
        term_raw = data.get("term")
        value_raw = data.get("value")
        term = term_raw if isinstance(term_raw, str) else None
        value = value_raw if isinstance(value_raw, str) else None
        if prefer_term:
            return term or value
        return value or term

    def walk(node: JSONObject) -> None:
        data_raw = node.get("data", {})
        data = data_raw if isinstance(data_raw, dict) else {}
        display_raw = data.get("display")
        display = display_raw if isinstance(display_raw, str) else None
        raw_value = choose_value(data)
        entries.append({"display": display, "value": raw_value})
        children_raw = node.get("children", [])
        children = children_raw if isinstance(children_raw, list) else []
        for child in children:
            if isinstance(child, dict):
                walk(child)

    if isinstance(vocabulary, dict) and vocabulary:
        walk(vocabulary)
    elif isinstance(vocabulary, list):
        for item in vocabulary:
            if isinstance(item, list) and item:
                value = str(item[0])
                display_from_list = str(item[1]) if len(item) > 1 else value
                entries.append({"display": display_from_list, "value": value})
            elif isinstance(item, dict):
                display_raw = item.get("display")
                display_from_dict = (
                    display_raw if isinstance(display_raw, str) else None
                )
                raw_value = choose_value(item)
                entries.append({"display": display_from_dict, "value": raw_value})
            else:
                entries.append({"display": str(item), "value": str(item)})
    return entries
