"""Canonical serialization helpers for persisted strategy state.

Goal: keep a single, shared definition for how we derive the persisted `steps`
list (StepData dicts) from various inputs (AST, graph snapshots, etc.).
"""

from __future__ import annotations

from typing import Any

from veupath_chatbot.domain.strategy.ast import from_dict

from .step_builders import build_steps_data_from_ast


def build_steps_data_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Build persisted steps list from a plan dict (AST payload)."""
    ast = from_dict(plan)
    return build_steps_data_from_ast(ast, search_name_fallback_to_transform=True)


def count_steps_in_plan(plan: dict[str, Any]) -> int:
    """Count steps in a plan without relying on persisted step lists."""
    try:
        ast = from_dict(plan)
    except Exception:
        return 0
    return len(ast.get_all_steps())


def build_steps_data_from_graph_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Build persisted steps list from a `graphSnapshot` payload.

    Normalizes whatever the UI sends into our canonical derived step shape.
    """
    steps_data: list[dict[str, Any]] = []
    snapshot_steps = snapshot.get("steps") or []
    if not isinstance(snapshot_steps, list):
        return steps_data

    for step in snapshot_steps:
        if not isinstance(step, dict):
            continue
        primary_input = step.get("primaryInputStepId")
        secondary_input = step.get("secondaryInputStepId")
        steps_data.append(
            {
                "id": step.get("id"),
                "kind": step.get("kind"),
                "displayName": step.get("displayName"),
                "searchName": step.get("searchName"),
                "recordType": step.get("recordType"),
                "parameters": step.get("parameters"),
                "operator": step.get("operator"),
                "primaryInputStepId": primary_input,
                "secondaryInputStepId": secondary_input,
                "filters": step.get("filters"),
                "analyses": step.get("analyses"),
                "reports": step.get("reports"),
            }
        )

    return steps_data

