"""Shared helpers for step sub-routers."""

from __future__ import annotations

from veupath_chatbot.domain.strategy.ast import (
    StepAnalysis,
    StepFilter,
    StepReport,
    from_dict,
)
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONArray, JSONObject, as_json_object


def get_steps_as_objects(steps: JSONArray) -> list[JSONObject]:
    """Convert JSONArray to list[JSONObject] with type checking."""
    result: list[JSONObject] = []
    for step in steps:
        if isinstance(step, dict):
            result.append(step)
    return result


def find_step(strategy_steps: list[JSONObject], step_id: str) -> JSONObject | None:
    for step in strategy_steps:
        if step.get("id") == step_id:
            return step
    return None


def update_plan(plan: JSONObject, step_id: str, updates: JSONObject) -> JSONObject:
    """Update a plan AST with step attachments."""
    try:
        ast = from_dict(plan)
    except Exception as exc:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": "", "message": str(exc), "code": "INVALID_STRATEGY"},
            ],
        ) from exc

    step = ast.get_step_by_id(step_id)
    if not step:
        return plan

    if "filters" in updates:
        filters_raw = updates["filters"]
        if isinstance(filters_raw, list):
            step.filters = [
                StepFilter(
                    name=str(f.get("name", "")),
                    value=f.get("value"),
                    disabled=bool(f.get("disabled", False)),
                )
                for f in filters_raw
                if isinstance(f, dict) and f.get("name") is not None
            ]
    if "analyses" in updates:
        analyses_raw = updates["analyses"]
        if isinstance(analyses_raw, list):
            step.analyses = [
                StepAnalysis(
                    analysis_type=str(
                        a.get("analysisType") or a.get("analysis_type", "")
                    ),
                    parameters=as_json_object(a.get("parameters"))
                    if isinstance(a.get("parameters"), dict)
                    else {},
                )
                for a in analyses_raw
                if isinstance(a, dict)
                and (a.get("analysisType") or a.get("analysis_type")) is not None
            ]
    if "reports" in updates:
        reports_raw = updates["reports"]
        if isinstance(reports_raw, list):
            step.reports = [
                StepReport(
                    report_name=str(
                        r.get("reportName") or r.get("report_name", "standard")
                    ),
                    config=as_json_object(r.get("config"))
                    if isinstance(r.get("config"), dict)
                    else {},
                )
                for r in reports_raw
                if isinstance(r, dict)
            ]
    return ast.to_dict()
