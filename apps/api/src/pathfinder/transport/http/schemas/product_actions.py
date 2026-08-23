"""Request schemas for product analytics actions."""

from typing import Literal

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONObject


class ProductActionRequest(CamelModel):
    """A user interaction to be recorded as a product signal."""

    action: Literal[
        "plan_approve",
        "plan_reject",
        "plan_suggest_changes",
        "plan_ask_question",
        "undo_turn",
        "assistant_regenerate",
    ]
    stream_id: str
    trace_id: str | None = None
    strategy_id: str | None = None
    plan_id: str | None = None
    entry_id: str | None = None
    message_group_id: str | None = None
    metadata: JSONObject | None = None
