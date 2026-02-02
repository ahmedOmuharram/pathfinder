"""Small helpers related to strategy graph metadata."""

from __future__ import annotations


def derive_graph_metadata(raw_goal: str) -> tuple[str, str]:
    clean = " ".join((raw_goal or "").strip().split())
    description = clean
    name = description
    if len(name) > 80:
        name = name[:77].rstrip() + "..."
    if not name:
        name = "Strategy Draft"
    return name, description

