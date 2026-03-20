"""Shared context dataclasses for orchestration and scheduling."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from kani.engines.base import BaseEngine
from kani.models import ChatMessage

from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.platform.types import JSONObject

EmitEvent = Callable[[JSONObject], Awaitable[None]]


@dataclass
class SubkaniContext:
    """Shared context for subkani task execution."""

    site_id: str
    strategy_session: StrategySession
    chat_history: list[ChatMessage]
    emit_event: EmitEvent
    subkani_timeout_seconds: int
    engine_factory: Callable[[], BaseEngine] | None = field(default=None)
