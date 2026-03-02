"""Chat stream event processing + persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from veupath_chatbot.persistence.models import Strategy
from veupath_chatbot.persistence.repo import StrategyRepository
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
)

from .event_handlers import handle_event, resolve_graph_id
from .finalization import finalize
from .sse import sse_error, sse_message_start
from .thinking import build_thinking_payload

logger = get_logger(__name__)


class ChatStreamProcessor:
    """Stateful processor for a single streamed chat turn."""

    def __init__(
        self,
        *,
        strategy_repo: StrategyRepository,
        site_id: str,
        user_id: UUID,
        strategy: Strategy,
        strategy_payload: JSONObject,
    ) -> None:
        self.strategy_repo = strategy_repo
        self.site_id = site_id
        self.user_id = user_id
        self.strategy = strategy
        self.strategy_payload = strategy_payload

        self.assistant_messages: list[str] = []
        self.citations: JSONArray = []
        self.planning_artifacts: JSONArray = []
        self.tool_calls: JSONArray = []
        self.tool_calls_by_id: dict[str, JSONObject] = {}
        self.subkani_calls: dict[str, JSONArray] = {}
        self.subkani_calls_by_id: dict[str, tuple[str, JSONObject]] = {}
        self.subkani_status: dict[str, str] = {}
        self.latest_plans: dict[str, JSONObject] = {}
        self.latest_graph_snapshots: dict[str, JSONObject] = {}
        self.pending_strategy_link: dict[str, JSONObject] = {}

        self.reasoning: str | None = None
        self.optimization_progress: JSONObject | None = None

        self.last_thinking_flush = datetime.now(UTC)
        self.thinking_dirty = False
        self.thinking_flush_interval = 2.0

    def resolve_graph_id(self, raw_id):
        """Resolve graph ID, converting JSONValue to str if needed.

        :param raw_id: Raw ID (str, None, or JSON).

        """
        return resolve_graph_id(raw_id)

    async def maybe_flush_thinking(self, *, force: bool = False) -> None:
        if not self.thinking_dirty:
            return
        now = datetime.now(UTC)
        if not force:
            elapsed = (now - self.last_thinking_flush).total_seconds()
            if elapsed < self.thinking_flush_interval:
                return
        payload = build_thinking_payload(
            self.tool_calls_by_id, self.subkani_calls, self.subkani_status
        )
        await self.strategy_repo.update_thinking(self.strategy.id, payload)
        self.last_thinking_flush = now
        self.thinking_dirty = False

    def start_event(self) -> str:
        return sse_message_start(
            strategy_id=str(self.strategy.id),
            strategy=self.strategy_payload,
        )

    async def on_event(self, event_type: str, event_data: JSONObject) -> str | None:
        """Process one semantic event; returns SSE line (or None if skipped)."""
        return await handle_event(self, event_type, event_data)

    async def finalize(self) -> list[str]:
        """Finalize the stream: persist messages + snapshots, and return extra SSE lines."""
        return await finalize(self)

    async def handle_exception(self, e: Exception) -> str:
        logger.error("Chat error", error=str(e))
        await self.strategy_repo.clear_thinking(self.strategy.id)
        return sse_error(str(e))
