"""Vocabulary utilities."""

from __future__ import annotations

import re
from typing import Any


def normalize_vocab_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def flatten_vocab(
    vocabulary: dict[str, Any] | list[Any], prefer_term: bool = False
) -> list[dict[str, str | None]]:
    entries: list[dict[str, str | None]] = []

    def choose_value(data: dict[str, Any]) -> str | None:
        if prefer_term:
            return data.get("term") or data.get("value")
        return data.get("value") or data.get("term")

    def walk(node: dict[str, Any]) -> None:
        data = node.get("data", {})
        display = data.get("display")
        raw_value = choose_value(data)
        entries.append({"display": display, "value": raw_value})
        for child in node.get("children", []) or []:
            walk(child)

    if isinstance(vocabulary, dict) and vocabulary:
        walk(vocabulary)
    elif isinstance(vocabulary, list):
        for item in vocabulary:
            if isinstance(item, list) and item:
                value = str(item[0])
                display = str(item[1]) if len(item) > 1 else value
                entries.append({"display": display, "value": value})
            elif isinstance(item, dict):
                display = item.get("display")
                raw_value = choose_value(item)
                entries.append({"display": display, "value": raw_value})
            else:
                entries.append({"display": str(item), "value": str(item)})
    return entries

