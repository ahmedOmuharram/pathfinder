"""Shared helpers for strategies routers."""

from datetime import UTC, datetime

from pathfinder.domain.strategy.ast import PlanStepNode, walk_step_tree
from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload
from pathfinder.persistence.models import Conversation
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.wdk import get_site
from pathfinder.transport.http.schemas import (
    ConversationResponse,
    StepResponse,
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


def step_response_from_plan(
    payload: StrategyPlanPayload, step: PlanStepNode
) -> StepResponse:
    """Build a StepResponse from a PlanStepNode using plan payload metadata."""
    counts = payload.step_counts or {}
    ids = payload.wdk_step_ids or {}
    validations = payload.step_validations or {}

    wdk_step_id = ids.get(step.id)
    if wdk_step_id is None and step.id.isdigit():
        wdk_step_id = int(step.id)

    return StepResponse(
        id=step.id,
        kind=step.infer_kind(),
        display_name=step.display_name or step.search_name,
        search_name=step.search_name,
        record_type=payload.record_type,
        parameters=step.parameters,
        operator=step.operator.value if step.operator else None,
        colocation_params=step.colocation_params,
        primary_input_step_id=step.primary_input.id if step.primary_input else None,
        secondary_input_step_id=step.secondary_input.id
        if step.secondary_input
        else None,
        estimated_size=counts.get(step.id),
        wdk_step_id=wdk_step_id,
        is_built=wdk_step_id is not None,
        is_filtered=bool(step.filters),
        validation=validations.get(step.id),
        filters=step.filters or None,
        analyses=step.analyses or None,
        reports=step.reports or None,
    )


def derive_steps_from_plan(
    payload: StrategyPlanPayload | None,
) -> list[StepResponse]:
    """Derive step responses from a typed plan payload. Returns [] if None.

    If the payload contains ``step_counts`` (stored during WDK detail fetch),
    each step's ``estimated_size`` is populated from it, enabling zero-cost count
    display for WDK-linked strategies.
    """
    if payload is None:
        return []
    return [
        step_response_from_plan(payload, step)
        for step in walk_step_tree(payload.root)
    ]


def extract_plan_description(
    payload: StrategyPlanPayload | None,
) -> str | None:
    """Extract description from a typed plan payload."""
    if payload is None:
        return None
    return payload.description


def extract_root_step_id(
    payload: StrategyPlanPayload | None,
    fallback_root_step_id: str | None = None,
) -> str | None:
    """Extract the root step ID from a typed plan payload."""
    if payload is not None:
        return payload.root.id
    return fallback_root_step_id


def _parse_plan_payload(plan_raw: JSONObject) -> StrategyPlanPayload | None:
    """Parse a raw JSON plan dict into a typed payload.

    Returns ``None`` when the dict is empty or invalid.
    """
    if not plan_raw or "root" not in plan_raw:
        return None
    try:
        return StrategyPlanPayload.model_validate(plan_raw)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse plan payload", error=str(exc))
        return None


def build_conversation_response(conversation: Conversation) -> ConversationResponse:
    """Build a ``ConversationResponse`` from a ``Conversation`` (detail view).

    Steps and rootStepId are derived from the plan at read time.
    """
    payload = _parse_plan_payload(conversation.plan)
    root_step_id = extract_root_step_id(payload)

    wdk_url = _compute_wdk_url(conversation.site_id, conversation.wdk_strategy_id)

    return ConversationResponse(
        id=conversation.id,
        name=conversation.name,
        title=conversation.name,
        description=extract_plan_description(payload),
        site_id=conversation.site_id,
        record_type=conversation.record_type,
        steps=derive_steps_from_plan(payload),
        root_step_id=root_step_id,
        wdk_strategy_id=conversation.wdk_strategy_id,
        wdk_url=wdk_url,
        gene_set_id=conversation.gene_set_id,
        experiment_id=conversation.experiment_id,
        is_saved=conversation.is_saved,
        pipeline=conversation.pipeline,
        created_at=conversation.created_at or datetime.now(UTC),
        updated_at=conversation.updated_at or datetime.now(UTC),
        dismissed_at=conversation.dismissed_at,
    )


def build_conversation_summary(
    conversation: Conversation,
    *,
    site_id: str = "",
) -> ConversationResponse:
    """Build a ``ConversationResponse`` (list view) from a ``Conversation``.

    Returns a summary with ``steps=[]`` and the denormalized fields populated.
    """
    effective_site_id = site_id or conversation.site_id
    wdk_url = _compute_wdk_url(effective_site_id, conversation.wdk_strategy_id)

    return ConversationResponse(
        id=conversation.id,
        name=conversation.name,
        title=conversation.name,
        site_id=effective_site_id,
        record_type=conversation.record_type,
        wdk_strategy_id=conversation.wdk_strategy_id,
        wdk_url=wdk_url,
        gene_set_id=conversation.gene_set_id,
        experiment_id=conversation.experiment_id,
        is_saved=conversation.is_saved,
        step_count=conversation.step_count,
        estimated_size=conversation.estimated_size,
        created_at=conversation.created_at or datetime.now(UTC),
        updated_at=conversation.updated_at or datetime.now(UTC),
        dismissed_at=conversation.dismissed_at,
    )
