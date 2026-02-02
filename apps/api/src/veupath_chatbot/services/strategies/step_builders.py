"""Strategy step construction helpers.

These functions are used to build the persisted step list from a Strategy AST.
They intentionally do not depend on HTTP DTOs.
"""

from typing import Any

from veupath_chatbot.domain.strategy.ast import SearchStep, StrategyAST


def _extract_input_ids(step_dict: dict[str, Any]) -> tuple[str | None, str | None]:
    step_type = step_dict.get("type")
    if step_type == "combine":
        left = step_dict.get("left", {})
        right = step_dict.get("right", {})
        return left.get("id"), right.get("id")
    if step_type == "transform":
        input_step = step_dict.get("input", {})
        return input_step.get("id"), None
    return None, None


def _step_identity_key(step: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(step.get("type") or ""),
        str(step.get("searchName") or ""),
        str(step.get("transformName") or ""),
        str(step.get("displayName") or ""),
        str(step.get("operator") or ""),
    )


def build_steps_data_from_ast(
    strategy_ast: StrategyAST,
    *,
    search_name_fallback_to_transform: bool = False,
) -> list[dict[str, Any]]:
    steps_data: list[dict[str, Any]] = []
    for step in strategy_ast.get_all_steps():
        step_dict = step.to_dict()
        primary_input_id, secondary_input_id = _extract_input_ids(step_dict)
        record_type = None
        if isinstance(step, SearchStep):
            record_type = step.record_type
        search_name = step_dict.get("searchName")
        if search_name_fallback_to_transform and not search_name:
            search_name = step_dict.get("transformName")
        steps_data.append(
            {
                "id": step.id,
                "type": step_dict.get("type"),
                "displayName": step_dict.get("displayName"),
                "searchName": search_name,
                "transformName": step_dict.get("transformName"),
                "recordType": record_type,
                "parameters": step_dict.get("parameters"),
                "operator": step_dict.get("operator"),
                "primaryInputStepId": primary_input_id,
                "secondaryInputStepId": secondary_input_id,
                "filters": step_dict.get("filters"),
                "analyses": step_dict.get("analyses"),
                "reports": step_dict.get("reports"),
            }
        )
    return steps_data

