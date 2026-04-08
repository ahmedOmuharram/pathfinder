"""Stream reconstruction engine: turn accumulation and event dispatch.

Provides the ``_TurnAccumulator`` class and per-event-type handlers
that transform raw Redis stream entries into complete chat messages.
The public read functions that drive Redis I/O live in
``platform.stream_readers``.
"""

from collections.abc import Callable
from datetime import UTC, datetime

from veupath_chatbot.platform.event_schemas import (
    AssistantMessageEventData,
    MessageEndEventData,
    ModelSelectedEventData,
    ReasoningEventData,
    ToolCallEndEventData,
    ToolCallStartEventData,
    UserMessageEventData,
)
from veupath_chatbot.platform.types import JSONObject

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _entry_id_to_iso(entry_id: bytes | str) -> str:
    """Convert a Redis stream entry ID (e.g. '1709234567890-0') to ISO 8601."""
    raw = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
    ms_str = raw.split("-")[0]
    try:
        ts = datetime.fromtimestamp(int(ms_str) / 1000, tz=UTC)
    except ValueError, OSError:
        ts = datetime.now(UTC)
    return ts.isoformat()


# ------------------------------------------------------------------
# Turn accumulator
# ------------------------------------------------------------------


class _TurnAccumulator:
    """Accumulates metadata for a single assistant turn."""

    __slots__ = (
        "citations",
        "model_id",
        "planning_artifacts",
        "reasoning",
        "tool_calls",
    )

    def __init__(self) -> None:
        self.tool_calls: list[JSONObject] = []
        self.citations: list[JSONObject] = []
        self.planning_artifacts: list[JSONObject] = []
        self.reasoning: str | None = None
        self.model_id: str | None = None

    def reset(self) -> None:
        self.tool_calls.clear()
        self.citations.clear()
        self.planning_artifacts.clear()
        self.reasoning = None
        self.model_id = None

    def build_assistant_message(
        self,
        data: JSONObject,
        entry_id: bytes | str,
    ) -> JSONObject:
        """Build a complete assistant message with accumulated metadata."""
        event = AssistantMessageEventData.model_validate(data)
        msg: JSONObject = {
            "role": "assistant",
            "content": event.content or "",
            "messageId": event.message_id,
            "timestamp": _entry_id_to_iso(entry_id),
        }
        if self.model_id:
            msg["modelId"] = self.model_id
        if self.tool_calls:
            msg["toolCalls"] = list(self.tool_calls)
        if self.citations:
            msg["citations"] = list(self.citations)
        if self.planning_artifacts:
            msg["planningArtifacts"] = list(self.planning_artifacts)
        if self.reasoning:
            msg["reasoning"] = self.reasoning
        # Preserve any fields directly on the event data.
        for key in ("citations", "planningArtifacts", "toolCalls", "reasoning"):
            if key in data and key not in msg:
                msg[key] = data[key]
        return msg


# ------------------------------------------------------------------
# Per-event-type handlers
# ------------------------------------------------------------------


def _handle_user_message(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = UserMessageEventData.model_validate(data)
    messages.append(
        {
            "role": "user",
            "content": event.content or "",
            "messageId": event.message_id,
            "timestamp": _entry_id_to_iso(entry_id),
        }
    )


def _handle_tool_call_start(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    # Arguments arrive from Redis as either a JSON string or an
    event = ToolCallStartEventData.model_validate(data)
    turn.tool_calls.append(
        {
            "id": event.id,
            "name": event.name,
            "arguments": event.arguments or {},
        }
    )


def _handle_tool_call_end(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = ToolCallEndEventData.model_validate(data)
    for tc in turn.tool_calls:
        if tc["id"] == event.id:
            tc["result"] = event.result
            break


# Citations and planning artifacts use pass-through extraction because their
# SSE models (CitationsEventData, PlanningArtifactEventData) validate nested
# items through strict inner models (CitationResponse, PlanningArtifactResponse)
# that require fields not always present in Redis replay data.  The stream
# reconstruction only accumulates these for later inclusion in the assistant
# message — no field mapping needed.
def _handle_citations(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    cites = data.get("citations")
    if isinstance(cites, list):
        turn.citations.extend(c for c in cites if isinstance(c, dict))


def _handle_planning_artifact(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    artifact = data.get("planningArtifact")
    if isinstance(artifact, dict):
        turn.planning_artifacts.append(artifact)


def _handle_reasoning(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = ReasoningEventData.model_validate(data)
    if event.reasoning:
        turn.reasoning = event.reasoning


def _handle_model_selected(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = ModelSelectedEventData.model_validate(data)
    turn.model_id = event.pipeline.planning.model_id


def _handle_assistant_message(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    messages.append(turn.build_assistant_message(data, entry_id))


# Type alias for stream event handler functions.
type _StreamEventHandler = Callable[
    [JSONObject, bytes | str, _TurnAccumulator, list[JSONObject]], None
]

# Dispatch table for stream reconstruction event handlers.
_STREAM_EVENT_HANDLERS: dict[str, _StreamEventHandler] = {
    "user_message": _handle_user_message,
    "tool_call_start": _handle_tool_call_start,
    "tool_call_end": _handle_tool_call_end,
    "citations": _handle_citations,
    "planning_artifact": _handle_planning_artifact,
    "reasoning": _handle_reasoning,
    "model_selected": _handle_model_selected,
    "assistant_message": _handle_assistant_message,
}


# ------------------------------------------------------------------
# Event processing
# ------------------------------------------------------------------


def _handle_message_end(
    data: JSONObject, messages: list[JSONObject], turn: _TurnAccumulator
) -> None:
    """Process a message_end event, attaching token usage to messages."""
    event = MessageEndEventData.model_validate(data)
    total = event.total_tokens or 0
    if total > 0:
        token_usage: JSONObject = {
            "promptTokens": event.prompt_tokens or 0,
            "completionTokens": event.completion_tokens or 0,
            "totalTokens": total,
            "cachedTokens": event.cached_tokens or 0,
            "toolCallCount": event.tool_call_count or 0,
            "registeredToolCount": event.registered_tool_count or 0,
            "llmCallCount": event.llm_call_count or 0,
            "estimatedCostUsd": event.estimated_cost_usd or 0.0,
            "modelId": event.model_id or "",
        }
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user" and "tokenUsage" not in messages[i]:
                messages[i]["tokenUsage"] = token_usage
                break
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant" and "tokenUsage" not in messages[i]:
                messages[i]["tokenUsage"] = token_usage
                break
    turn.reset()


def _process_stream_event(
    event_type: str,
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    """Process a single Redis stream event, mutating *turn* and *messages*.

    Uses a dispatch table for most event types; a few special cases
    (message_start, message_end) that need the turn/messages pair in
    non-standard ways are handled inline.
    """
    if event_type == "message_start":
        turn.reset()
        return

    if event_type == "message_end":
        _handle_message_end(data, messages, turn)
        return

    handler = _STREAM_EVENT_HANDLERS.get(event_type)
    if handler:
        handler(data, entry_id, turn, messages)


