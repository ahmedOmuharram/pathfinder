"""SSE event collector for integration tests.

Sends a chat request through the full HTTP endpoint and collects all
SSE events into a structured list for assertion.
"""

import json
from dataclasses import dataclass, field

import httpx

from veupath_chatbot.platform.types import JSONObject


@dataclass
class SSEEvent:
    """A single parsed SSE event."""

    type: str
    data: JSONObject


@dataclass
class ChatStreamResult:
    """All events collected from one chat SSE stream."""

    events: list[SSEEvent] = field(default_factory=list)
    http_status: int = 0

    @property
    def event_types(self) -> list[str]:
        return [e.type for e in self.events]

    def events_of_type(self, event_type: str) -> list[SSEEvent]:
        return [e for e in self.events if e.type == event_type]

    def first_event(self, event_type: str) -> SSEEvent | None:
        for e in self.events:
            if e.type == event_type:
                return e
        return None

    @property
    def tool_calls(self) -> list[tuple[SSEEvent, SSEEvent]]:
        """Return paired (tool_call_start, tool_call_end) events."""
        starts: dict[str, SSEEvent] = {}
        pairs: list[tuple[SSEEvent, SSEEvent]] = []
        for e in self.events:
            if e.type == "tool_call_start":
                call_id = e.data.get("id")
                if isinstance(call_id, str):
                    starts[call_id] = e
            elif e.type == "tool_call_end":
                call_id = e.data.get("id")
                if isinstance(call_id, str) and call_id in starts:
                    pairs.append((starts[call_id], e))
        return pairs

    @property
    def assistant_content(self) -> str:
        """Concatenated content of all assistant_message events."""
        parts: list[str] = []
        for e in self.events:
            if e.type == "assistant_message":
                content = e.data.get("content")
                if isinstance(content, str):
                    parts.append(content)
        return "\n".join(parts)

    @property
    def strategy_id(self) -> str | None:
        """Extract the strategy ID from the message_start event."""
        start = self.first_event("message_start")
        if start:
            sid = start.data.get("strategyId")
            if isinstance(sid, str):
                return sid
            strategy = start.data.get("strategy")
            if isinstance(strategy, dict):
                sid = strategy.get("id")
                if isinstance(sid, str):
                    return sid
        return None


def _parse_sse_text(text: str) -> list[SSEEvent]:
    """Parse raw SSE text into structured events.

    :param text: Raw SSE text to parse.
    :returns: List of parsed SSE events.
    """
    events: list[SSEEvent] = []
    for raw_part in text.split("\n\n"):
        part = raw_part.strip()
        if not part:
            continue
        lines = [ln for ln in part.split("\n") if ln.strip()]
        et: str | None = None
        data_str: str | None = None
        for ln in lines:
            if ln.startswith("event:"):
                et = ln[len("event:") :].strip()
            elif ln.startswith("data:"):
                data_str = ln[len("data:") :].strip()
        if et and data_str is not None:
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"_raw": data_str}
            events.append(
                SSEEvent(
                    type=et, data=data if isinstance(data, dict) else {"_raw": data}
                )
            )
    return events


async def collect_chat_stream(
    client: httpx.AsyncClient,
    *,
    message: str,
    site_id: str = "veupathdb",
    strategy_id: str | None = None,
    request_timeout: float = 120.0,
) -> ChatStreamResult:
    """Send a chat request and collect all SSE events.

    Uses the CQRS pattern: POST /chat returns 202 with an operationId,
    then GET /operations/{operationId}/subscribe streams SSE events.

    :param client: HTTP client for the request.
    :param message: Chat message to send.
    :param site_id: VEuPathDB site identifier (default ``"veupathdb"``).
    :param strategy_id: Optional strategy ID.
    :param request_timeout: Request timeout in seconds.
    :returns: Collected SSE events and HTTP status.
    """
    payload: JSONObject = {
        "siteId": site_id,
        "message": message,
    }
    if strategy_id:
        payload["strategyId"] = strategy_id

    result = ChatStreamResult()

    # Step 1: Start the chat operation.
    resp = await client.post("/api/v1/chat", json=payload, timeout=request_timeout)
    result.http_status = resp.status_code
    if resp.status_code != 202:
        result.events.append(
            SSEEvent(
                type="http_error",
                data={"status": resp.status_code, "body": resp.text},
            )
        )
        return result

    body = resp.json()
    operation_id = body.get("operationId")
    if not operation_id:
        result.events.append(
            SSEEvent(
                type="http_error", data={"status": 202, "body": "missing operationId"}
            )
        )
        return result

    # Step 2: Subscribe to the operation SSE stream.
    collected = ""
    async with client.stream(
        "GET",
        f"/api/v1/operations/{operation_id}/subscribe",
        timeout=request_timeout,
    ) as sse_resp:
        if sse_resp.status_code != 200:
            raw = ""
            async for chunk in sse_resp.aiter_text():
                raw += chunk
            result.events.append(
                SSEEvent(
                    type="http_error",
                    data={"status": sse_resp.status_code, "body": raw},
                )
            )
            return result

        async for chunk in sse_resp.aiter_text():
            collected += chunk
            if "event: message_end" in collected:
                break

    result.events = _parse_sse_text(collected)
    return result
