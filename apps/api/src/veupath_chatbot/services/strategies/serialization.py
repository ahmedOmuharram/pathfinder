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


def build_steps_data_from_graph_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Build persisted steps list from a `graphSnapshot` payload.

    The `graphSnapshot.steps[*]` shape uses `inputStepIds`, which we normalize into
    `primaryInputStepId` / `secondaryInputStepId`.
    """
    steps_data: list[dict[str, Any]] = []
    snapshot_steps = snapshot.get("steps") or []
    if not isinstance(snapshot_steps, list):
        return steps_data

    for step in snapshot_steps:
        if not isinstance(step, dict):
            continue
        input_ids = step.get("inputStepIds") or []
        if not isinstance(input_ids, list):
            input_ids = []
        steps_data.append(
            {
                "id": step.get("id"),
                "type": step.get("type"),
                "displayName": step.get("displayName"),
                "searchName": step.get("searchName") or step.get("transformName"),
                "transformName": step.get("transformName"),
                "recordType": step.get("recordType"),
                "parameters": step.get("parameters"),
                "operator": step.get("operator"),
                "primaryInputStepId": input_ids[0] if len(input_ids) > 0 else None,
                "secondaryInputStepId": input_ids[1] if len(input_ids) > 1 else None,
                "filters": step.get("filters"),
                "analyses": step.get("analyses"),
                "reports": step.get("reports"),
            }
        )

    return steps_data

