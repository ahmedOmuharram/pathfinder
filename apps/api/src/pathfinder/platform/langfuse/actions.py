"""Record product interaction events in Langfuse."""

from __future__ import annotations

from typing import Literal

import langfuse.api

from pathfinder.platform.langfuse.client import get_langfuse
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)

ProductActionName = Literal[
    "plan_approve",
    "plan_reject",
    "plan_suggest_changes",
    "plan_ask_question",
    "undo_turn",
    "assistant_regenerate",
]

_LANGFUSE_ERRORS = (langfuse.api.Error, ValueError, OSError)


class ProductActionEvent(CamelModel):
    """Structured product interaction payload for Langfuse."""

    action: ProductActionName
    stream_id: str
    trace_id: str | None = None
    strategy_id: str | None = None
    plan_id: str | None = None
    entry_id: str | None = None
    message_group_id: str | None = None
    operation_id: str | None = None
    metadata: JSONObject | None = None


def _clean_payload(payload: dict[str, object | None]) -> JSONObject:
    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


def record_product_action(event: ProductActionEvent) -> None:
    """Record a user/product action in Langfuse.

    When ``trace_id`` is available the event is attached to the originating turn.
    Otherwise the event is still emitted with lineage metadata so it remains
    queryable as a standalone product signal.
    """

    client = get_langfuse()
    if client is None:
        logger.debug(
            "Product action discarded (Langfuse disabled)",
            action=event.action,
        )
        return

    event_input = _clean_payload(
        {
            "action": event.action,
            "stream_id": event.stream_id,
            "strategy_id": event.strategy_id,
            "plan_id": event.plan_id,
            "entry_id": event.entry_id,
            "message_group_id": event.message_group_id,
            "operation_id": event.operation_id,
        }
    )
    event_metadata = _clean_payload(
        {
            "stream_id": event.stream_id,
            "strategy_id": event.strategy_id,
            "plan_id": event.plan_id,
            "entry_id": event.entry_id,
            "message_group_id": event.message_group_id,
            "operation_id": event.operation_id,
            **(event.metadata or {}),
        }
    )

    try:
        client.create_event(
            trace_context={"trace_id": event.trace_id} if event.trace_id else None,
            name=f"product.{event.action}",
            input=event_input,
            metadata=event_metadata,
        )
        logger.info(
            "Product action recorded",
            action=event.action,
            stream_id=event.stream_id,
            trace_id=event.trace_id,
            strategy_id=event.strategy_id,
            plan_id=event.plan_id,
            entry_id=event.entry_id,
            operation_id=event.operation_id,
        )
    except _LANGFUSE_ERRORS:
        logger.warning(
            "Failed to record product action",
            action=event.action,
            trace_id=event.trace_id,
            exc_info=True,
        )
