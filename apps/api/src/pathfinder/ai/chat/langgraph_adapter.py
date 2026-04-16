from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field

from pydantic_ai.messages import (
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
)
from shared_py.stream_events import (
    CompletedToolCall,
    MessagesCompleteEvent,
    MessagesPartialEvent,
    StreamEvent,
    ToolCallDelta,
)


@dataclass
class _PendingToolCall:
    id: str
    name: str
    args_buffer: str = ""


@dataclass
class LangGraphEventAdapter:
    """Stateful translator: pydantic-ai agent events -> StreamEvents.

    Usage:
        adapter = LangGraphEventAdapter(message_id=str(uuid4()))
        for pai_event in agent_event_iter:
            for out in adapter.handle(pai_event):
                writer({"stream_event": out})
        writer({"stream_event": adapter.finalize()})
    """

    message_id: str
    _text_buffer: str = ""
    _reasoning_buffer: str = ""
    _tool_calls: dict[str, _PendingToolCall] = field(default_factory=dict)

    def handle(self, event: object) -> Iterator[StreamEvent]:
        if isinstance(event, PartStartEvent):
            yield from self._handle_part_start(event)
        elif isinstance(event, PartDeltaEvent):
            yield from self._handle_part_delta(event)
        elif isinstance(event, FunctionToolCallEvent):
            return
        elif isinstance(event, FunctionToolResultEvent):
            yield from self._handle_tool_result(event)
        elif isinstance(event, FinalResultEvent):
            return

    def _handle_part_start(self, event: PartStartEvent) -> Iterator[StreamEvent]:
        part = event.part
        if isinstance(part, TextPart):
            self._text_buffer += part.content
            if part.content:
                yield MessagesPartialEvent(
                    message_id=self.message_id, delta=part.content
                )
        elif isinstance(part, ThinkingPart):
            self._reasoning_buffer += part.content
            if part.content:
                yield MessagesPartialEvent(
                    message_id=self.message_id, reasoning_delta=part.content
                )
        elif isinstance(part, ToolCallPart):
            args_str = part.args if isinstance(part.args, str) else ""
            self._tool_calls[part.tool_call_id] = _PendingToolCall(
                id=part.tool_call_id,
                name=part.tool_name,
                args_buffer=args_str,
            )
            yield MessagesPartialEvent(
                message_id=self.message_id,
                tool_call_deltas=[
                    ToolCallDelta(
                        tool_call_id=part.tool_call_id,
                        tool_name=part.tool_name,
                        arguments_delta=args_str,
                    )
                ],
            )

    def _handle_part_delta(self, event: PartDeltaEvent) -> Iterator[StreamEvent]:
        delta = event.delta
        if isinstance(delta, TextPartDelta):
            self._text_buffer += delta.content_delta
            yield MessagesPartialEvent(
                message_id=self.message_id, delta=delta.content_delta
            )
        elif isinstance(delta, ThinkingPartDelta):
            if delta.content_delta is None:
                return
            self._reasoning_buffer += delta.content_delta
            yield MessagesPartialEvent(
                message_id=self.message_id, reasoning_delta=delta.content_delta
            )
        elif isinstance(delta, ToolCallPartDelta):
            if delta.tool_call_id is None:
                return
            args_str = delta.args_delta if isinstance(delta.args_delta, str) else ""
            pending = self._tool_calls.get(delta.tool_call_id)
            if pending is not None:
                pending.args_buffer += args_str
            yield MessagesPartialEvent(
                message_id=self.message_id,
                tool_call_deltas=[
                    ToolCallDelta(
                        tool_call_id=delta.tool_call_id,
                        arguments_delta=args_str,
                    )
                ],
            )

    def _handle_tool_result(
        self, event: FunctionToolResultEvent
    ) -> Iterator[StreamEvent]:
        result = event.result
        if isinstance(result, ToolReturnPart):
            yield MessagesCompleteEvent(
                message_id=f"{self.message_id}-tool-{result.tool_call_id}",
                role="tool",
                tool_call_id=result.tool_call_id,
                name=result.tool_name,
                content=_coerce_tool_content(result.content),
            )

    def finalize(self) -> MessagesCompleteEvent:
        completed_calls = [
            CompletedToolCall(
                id=call.id,
                name=call.name,
                arguments=_parse_args(call.args_buffer),
            )
            for call in self._tool_calls.values()
        ]
        return MessagesCompleteEvent(
            message_id=self.message_id,
            role="ai",
            content=self._text_buffer,
            reasoning=self._reasoning_buffer,
            tool_calls=completed_calls,
        )


def _parse_args(raw: str) -> dict[str, object]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _coerce_tool_content(content: object) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, default=str)
