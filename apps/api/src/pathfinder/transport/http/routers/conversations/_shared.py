"""Shared helpers for strategies routers."""

from datetime import UTC, datetime
from decimal import Decimal

from pathfinder.ai.specialists.types import SpecialistMode
from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import Conversation
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.strategies.schemas import (
    step_response_from_strategy_ast,
)
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


def derive_steps_from_strategy_ast(
    payload: StrategyAst | None,
) -> list[StepResponse]:
    """Derive step responses from a typed plan payload. Returns [] if None.

    If the payload contains ``step_counts`` (stored during WDK detail fetch),
    each step's ``estimated_size`` is populated from it, enabling zero-cost count
    display for WDK-linked strategies.
    """
    if payload is None:
        return []
    return [
        step_response_from_strategy_ast(payload, step)
        for step in walk_step_tree(payload.root)
    ]


def extract_strategy_description(
    payload: StrategyAst | None,
) -> str | None:
    """Extract description from a typed plan payload."""
    if payload is None:
        return None
    return payload.description


def extract_root_step_id(
    payload: StrategyAst | None,
    fallback_root_step_id: str | None = None,
) -> str | None:
    """Extract the root step ID from a typed plan payload."""
    if payload is not None:
        return payload.root.id
    return fallback_root_step_id


def _parse_strategy_ast(plan_raw: JSONObject) -> StrategyAst | None:
    """Parse a raw JSON plan dict into a typed payload.

    Returns ``None`` when the dict is empty or invalid.
    """
    if not plan_raw or "root" not in plan_raw:
        return None
    try:
        return StrategyAst.model_validate(plan_raw)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse plan payload", error=str(exc))
        return None


def _parse_specialist_mode(raw: JSONObject | None) -> SpecialistMode | None:
    """Parse the persisted ``specialist_mode`` JSON column into the typed model."""
    if raw is None:
        return None
    try:
        return SpecialistMode.model_validate(raw)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse specialist_mode payload", error=str(exc))
        return None


def build_conversation_response(
    conversation: Conversation,
    *,
    total_tokens: int = 0,
    total_cost_usd: Decimal | None = None,
) -> ConversationResponse:
    """Build a ``ConversationResponse`` from a ``Conversation`` (detail view).

    Steps and rootStepId are derived from the plan at read time. ``total_tokens``
    and ``total_cost_usd`` surface cumulative chat usage for the footer under
    the composer; pass them after aggregating ``Message.metadata.usage``.
    """
    payload = _parse_strategy_ast(conversation.strategy_ast)
    root_step_id = extract_root_step_id(payload)

    wdk_url = _compute_wdk_url(conversation.site_id, conversation.wdk_strategy_id)

    return ConversationResponse(
        id=conversation.id,
        name=conversation.name,
        title=conversation.name,
        description=extract_strategy_description(payload),
        site_id=conversation.site_id,
        record_type=conversation.record_type,
        steps=derive_steps_from_strategy_ast(payload),
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
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd is not None else Decimal(0),
        supervisor_model_id=conversation.supervisor_model_id,
        parent_conversation_id=conversation.parent_conversation_id,
        parent_message_id=conversation.parent_message_id,
        specialist_mode=_parse_specialist_mode(conversation.specialist_mode),
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
        parent_conversation_id=conversation.parent_conversation_id,
        parent_message_id=conversation.parent_message_id,
    )
