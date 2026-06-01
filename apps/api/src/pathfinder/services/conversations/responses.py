"""Conversation response DTOs + builders.

Owns the ``Conversation`` ORM → response-DTO mapping so transport returns
these without importing persistence or building them itself.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import Conversation
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.strategies.schemas import (
    StepResponse,
    step_response_from_strategy_ast,
)
from pathfinder.services.wdk import get_site

logger = get_logger(__name__)


class ConversationResponse(CamelModel):
    id: UUID
    name: str
    title: str | None = None
    description: str | None = None
    site_id: str
    record_type: str | None
    steps: list[StepResponse] = Field(default_factory=list)
    root_step_id: str | None = Field(default=None)
    wdk_strategy_id: int | None = Field(default=None)
    is_saved: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime
    step_count: int | None = Field(default=None)
    estimated_size: int | None = Field(default=None)
    wdk_url: str | None = Field(default=None)
    gene_set_id: str | None = Field(default=None)
    experiment_id: str | None = Field(default=None)
    dismissed_at: datetime | None = Field(default=None)
    total_tokens: int = Field(default=0)
    total_cost_usd: Decimal = Field(default_factory=lambda: Decimal(0))
    parent_conversation_id: UUID | None = Field(default=None)
    parent_message_id: UUID | None = Field(default=None)


def _compute_wdk_url(site_id: str, wdk_strategy_id: int | None) -> str | None:
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


def derive_steps_from_strategy_ast(payload: StrategyAst | None) -> list[StepResponse]:
    if payload is None:
        return []
    return [
        step_response_from_strategy_ast(payload, step)
        for step in walk_step_tree(payload.root)
    ]


def extract_strategy_description(payload: StrategyAst | None) -> str | None:
    if payload is None:
        return None
    return payload.description


def extract_root_step_id(
    payload: StrategyAst | None,
    fallback_root_step_id: str | None = None,
) -> str | None:
    if payload is not None:
        return payload.root.id
    return fallback_root_step_id


def _parse_strategy_ast(plan_raw: JSONObject) -> StrategyAst | None:
    if not plan_raw or "root" not in plan_raw:
        return None
    try:
        return StrategyAst.model_validate(plan_raw)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse plan payload", error=str(exc))
        return None


def build_conversation_response(
    conversation: Conversation,
    *,
    total_tokens: int = 0,
    total_cost_usd: Decimal | None = None,
) -> ConversationResponse:
    """Build a detail-view ``ConversationResponse`` from a ``Conversation``."""
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
        created_at=conversation.created_at or datetime.now(UTC),
        updated_at=conversation.updated_at or datetime.now(UTC),
        dismissed_at=conversation.dismissed_at,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd is not None else Decimal(0),
        parent_conversation_id=conversation.parent_conversation_id,
        parent_message_id=conversation.parent_message_id,
    )


def build_conversation_summary(
    conversation: Conversation,
    *,
    site_id: str = "",
) -> ConversationResponse:
    """Build a list-view ``ConversationResponse`` (steps=[]) from a ``Conversation``."""
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
