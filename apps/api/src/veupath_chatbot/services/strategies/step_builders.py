"""Strategy step construction helpers.

These functions are used to build the persisted step list from a Strategy AST.
They intentionally do not depend on HTTP DTOs.
"""

from typing import Any

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST


def _extract_input_ids(step_dict: dict[str, Any]) -> tuple[str | None, str | None]:
    primary = step_dict.get("primaryInput") or {}
    secondary = step_dict.get("secondaryInput") or {}
    primary_id = primary.get("id") if isinstance(primary, dict) else None
    secondary_id = secondary.get("id") if isinstance(secondary, dict) else None
    if primary_id and secondary_id:
        return primary_id, secondary_id
    if primary_id:
        return primary_id, None
    return None, None


def _step_identity_key(step: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(step.get("kind") or ""),
        str(step.get("searchName") or ""),
        "",
        str(step.get("displayName") or ""),
        str(step.get("operator") or ""),
    )


def build_steps_data_from_ast(
    strategy_ast: StrategyAST,
    *,
    search_name_fallback_to_transform: bool = False,  # kept for API compatibility; no-op now
) -> list[dict[str, Any]]:
    steps_data: list[dict[str, Any]] = []
    for step in strategy_ast.get_all_steps():
        step_dict = step.to_dict()
        primary_input_id, secondary_input_id = _extract_input_ids(step_dict)
        record_type = strategy_ast.record_type or None
        search_name = step_dict.get("searchName")
        wdk_step_id: int | None = None
        if isinstance(step.id, str) and step.id.isdigit():
            try:
                wdk_step_id = int(step.id)
            except Exception:
                wdk_step_id = None
        steps_data.append(
            {
                "id": step.id,
                "kind": step.infer_kind(),
                "displayName": step_dict.get("displayName"),
                "searchName": search_name,
                "recordType": record_type,
                "parameters": step_dict.get("parameters"),
                "operator": step_dict.get("operator"),
                "colocationParams": step_dict.get("colocationParams"),
                "primaryInputStepId": primary_input_id,
                "secondaryInputStepId": secondary_input_id,
                "resultCount": None,
                "wdkStepId": wdk_step_id,
                "filters": step_dict.get("filters"),
                "analyses": step_dict.get("analyses"),
                "reports": step_dict.get("reports"),
            }
        )
    return steps_data

