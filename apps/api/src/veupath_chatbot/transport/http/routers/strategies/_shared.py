"""Shared helpers for strategies routers."""

from datetime import UTC, datetime

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.integrations.veupathdb.factory import get_site
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


def _compute_wdk_url(site_id: str, wdk_strategy_id: int | None) -> str | None:
    """Compute the WDK URL for a strategy if possible.

    Returns ``None`` when the strategy has no WDK ID or the site is unknown.
    """
    if wdk_strategy_id is None or not site_id:
        return None
    try:
        site = get_site(site_id)
        return site.strategy_url(wdk_strategy_id)
    except (KeyError, ValueError) as exc:
        logger.debug(
            "Failed to compute WDK URL for strategy",
            site_id=site_id,
            wdk_strategy_id=wdk_strategy_id,
            error=str(exc),
        )
        return None


def build_step_response(step: JSONObject) -> StepResponse:
    """Build a StepResponse from a step dict."""
    return StepResponse.model_validate(step)


def derive_steps_from_plan(plan: JSONObject) -> list[StepResponse]:
    """Derive step responses from a plan dict. Returns [] if plan is empty/invalid.

    If the plan contains a ``stepCounts`` dict (stored during WDK detail fetch),
    each step's ``resultCount`` is populated from it, enabling zero-cost count
    display for WDK-linked strategies.
    """
    if not plan or not isinstance(plan, dict) or "root" not in plan:
        return []
    try:
        ast = StrategyAST.model_validate(plan)
        steps_data = build_steps_data_from_ast(ast)

        # Inject stored step counts from plan metadata.
        step_counts = plan.get("stepCounts")
        if isinstance(step_counts, dict):
            for s in steps_data:
                if not isinstance(s, dict):
                    continue
                sid = s.get("id")
                if isinstance(sid, str) and sid in step_counts:
                    count = step_counts[sid]
                    if isinstance(count, int):
                        s["resultCount"] = count

        return [build_step_response(s) for s in steps_data if isinstance(s, dict)]
    except (ValueError, KeyError, TypeError) as exc:
        logger.exception(
            "derive_steps_from_plan failed",
            error=str(exc),
            error_type=type(exc).__name__,
            plan_keys=list(plan.keys()) if isinstance(plan, dict) else None,
        )
        return []


def extract_plan_description(plan: JSONObject) -> str | None:
    """Extract description from a plan dict."""
    desc_raw = plan.get("description")
    return desc_raw if isinstance(desc_raw, str) else None


def parse_thinking(raw: JSONObject | None) -> ThinkingResponse | None:
    """Parse a strategy's ``thinking`` JSON object into a response model.

    Returns ``None`` on empty input or validation errors.
    """
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return ThinkingResponse.model_validate(raw)
    except (ValueError, TypeError, KeyError) as exc:
        logger.debug("Failed to parse thinking response", error=str(exc))
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
    root_step_id = extract_root_step_id(plan, projection.root_step_id)

    msg_responses: list[MessageResponse] | None = None
    if messages:
        validated: list[MessageResponse] = []
        for i, m in enumerate(messages):
            if not isinstance(m, dict):
                continue
            try:
                validated.append(MessageResponse.model_validate(m))
            except (ValueError, TypeError, KeyError) as exc:
                logger.warning(
                    "Skipping malformed message during projection build",
                    index=i,
                    role=m.get("role"),
                    error=str(exc),
                )
        msg_responses = validated or None

    thinking_response = parse_thinking(thinking)

    wdk_url = _compute_wdk_url(projection.site_id, projection.wdk_strategy_id)

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
        wdkUrl=wdk_url,
        geneSetId=projection.gene_set_id,
        isSaved=projection.is_saved,
        messages=msg_responses,
        thinking=thinking_response,
        modelId=projection.model_id,
        createdAt=projection.stream.created_at
        if projection.stream
        else datetime.now(UTC),
        updatedAt=projection.updated_at or datetime.now(UTC),
        dismissedAt=projection.dismissed_at,
    )


def build_projection_summary(
    projection: StreamProjection,
    *,
    site_id: str = "",
) -> StrategyResponse:
    """Build a ``StrategyResponse`` (list view) from a StreamProjection.

    Returns a StrategyResponse with ``steps=[]`` and summary fields populated.
    """
    effective_site_id = site_id or projection.site_id
    wdk_url = _compute_wdk_url(effective_site_id, projection.wdk_strategy_id)

    return StrategyResponse(
        id=projection.stream_id,
        name=projection.name,
        title=projection.name,
        siteId=effective_site_id,
        recordType=projection.record_type,
        wdkStrategyId=projection.wdk_strategy_id,
        wdkUrl=wdk_url,
        geneSetId=projection.gene_set_id,
        isSaved=projection.is_saved,
        stepCount=projection.step_count,
        resultCount=projection.result_count,
        createdAt=projection.stream.created_at
        if projection.stream
        else datetime.now(UTC),
        updatedAt=projection.updated_at or datetime.now(UTC),
        dismissedAt=projection.dismissed_at,
    )
