"""Shared helpers for strategies routers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from veupath_chatbot.domain.strategy.ast import from_dict as parse_plan
from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.step_builders import build_steps_data_from_ast
from veupath_chatbot.transport.http.schemas import (
    MessageResponse,
    StepResponse,
    StrategyResponse,
    ThinkingResponse,
)

logger = get_logger(__name__)


def build_step_response(step: JSONObject) -> StepResponse:
    """Build a StepResponse from a step dict."""
    return StepResponse.model_validate(cast(dict[str, object], step))


def derive_steps_from_plan(plan: JSONObject) -> list[StepResponse]:
    """Derive step responses from a plan dict. Returns [] if plan is empty/invalid."""
    if not plan or not isinstance(plan, dict) or "root" not in plan:
        return []
    try:
        ast = parse_plan(plan)
        steps_data = build_steps_data_from_ast(ast)
        return [build_step_response(s) for s in steps_data if isinstance(s, dict)]
    except ValueError, KeyError, TypeError:
        return []


def extract_plan_description(plan: JSONObject) -> str | None:
    """Extract ``plan["metadata"]["description"]`` with isinstance guards."""
    metadata_raw = plan.get("metadata")
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
    desc_raw = metadata.get("description")
    return desc_raw if isinstance(desc_raw, str) else None


def parse_thinking(raw: JSONObject | None) -> ThinkingResponse | None:
    """Parse a strategy's ``thinking`` JSON object into a response model.

    Returns ``None`` on empty input or validation errors.
    """
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return ThinkingResponse.model_validate(raw)
    except Exception:
        return None


def extract_root_step_id(
    plan: JSONObject, fallback_root_step_id: str | None
) -> str | None:
    """Extract ``plan["root"]["id"]`` with isinstance guards.

    Falls back to ``fallback_root_step_id`` when the plan doesn't contain one.
    """
    root_raw = plan.get("root")
    root = root_raw if isinstance(root_raw, dict) else {}
    root_id_raw = root.get("id")
    root_step_id = root_id_raw if isinstance(root_id_raw, str) else None
    return root_step_id or fallback_root_step_id


def build_projection_response(
    projection: StreamProjection,
    *,
    messages: list[JSONObject] | None = None,
    thinking: JSONObject | None = None,
) -> StrategyResponse:
    """Build a ``StrategyResponse`` from a StreamProjection + Redis data.

    Steps and rootStepId are derived from the plan at read time.
    """
    plan: JSONObject = projection.plan if isinstance(projection.plan, dict) else {}
    root_step_id = extract_root_step_id(plan, None)

    msg_responses: list[MessageResponse] | None = None
    if messages:
        validated: list[MessageResponse] = []
        for i, m in enumerate(messages):
            if not isinstance(m, dict):
                continue
            try:
                validated.append(MessageResponse.model_validate(m))
            except Exception as exc:
                logger.warning(
                    "Skipping malformed message during projection build",
                    index=i,
                    role=m.get("role"),
                    error=str(exc),
                )
        msg_responses = validated or None

    thinking_response = parse_thinking(thinking)

    return StrategyResponse(
        id=projection.stream_id,
        name=projection.name,
        title=projection.name,
        description=extract_plan_description(plan),
        siteId=projection.site_id,
        recordType=projection.record_type,
        steps=derive_steps_from_plan(plan),
        rootStepId=root_step_id,
        wdkStrategyId=projection.wdk_strategy_id,
        isSaved=projection.is_saved,
        messages=msg_responses,
        thinking=thinking_response,
        modelId=projection.model_id,
        createdAt=projection.stream.created_at
        if projection.stream
        else datetime.now(UTC),
        updatedAt=projection.updated_at or datetime.now(UTC),
    )


def build_projection_summary(
    projection: StreamProjection,
    *,
    site_id: str = "",
) -> StrategyResponse:
    """Build a ``StrategyResponse`` (list view) from a StreamProjection.

    Returns a StrategyResponse with ``steps=[]`` and summary fields populated.
    """
    return StrategyResponse(
        id=projection.stream_id,
        name=projection.name,
        title=projection.name,
        siteId=site_id or projection.site_id,
        recordType=projection.record_type,
        wdkStrategyId=projection.wdk_strategy_id,
        isSaved=projection.is_saved,
        stepCount=projection.step_count,
        resultCount=projection.result_count,
        createdAt=projection.stream.created_at
        if projection.stream
        else datetime.now(UTC),
        updatedAt=projection.updated_at or datetime.now(UTC),
    )
