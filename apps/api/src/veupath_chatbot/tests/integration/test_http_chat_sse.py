import json

import httpx
import pytest

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedEngineFactory,
    ScriptedToolCall,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream


def _parse_sse_events(text: str) -> list[tuple[str, JSONObject]]:
    events: list[tuple[str, JSONObject]] = []
    for part in text.split("\n\n"):
        part = part.strip()
        if not part:
            continue
        lines = [ln for ln in part.split("\n") if ln.strip()]
        et = None
        data = None
        for ln in lines:
            if ln.startswith("event:"):
                et = ln[len("event:") :].strip()
            if ln.startswith("data:"):
                data = ln[len("data:") :].strip()
        if et and data is not None:
            events.append((et, json.loads(data)))
    return events


async def test_chat_stream_sse_with_mock_provider(
    authed_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATHFINDER_CHAT_PROVIDER", "mock")

    payload = {
        "siteId": "plasmodb",
        "message": "hello",
    }

    collected = ""
    async with authed_client.stream("POST", "/api/v1/chat", json=payload) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

        async for chunk in resp.aiter_text():
            collected += chunk
            if "event: message_end" in collected:
                break

    events = _parse_sse_events(collected)
    types = [t for t, _ in events]
    assert "message_start" in types
    assert "assistant_delta" in types
    assert "assistant_message" in types
    assert types[-1] == "message_end"


async def test_execute_stream_can_emit_planning_artifact_with_mock_provider(
    authed_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATHFINDER_CHAT_PROVIDER", "mock")

    payload = {
        "siteId": "plasmodb",
        "message": "please emit artifact",
    }

    collected = ""
    async with authed_client.stream("POST", "/api/v1/chat", json=payload) as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            collected += chunk
            if "event: message_end" in collected:
                break

    events = _parse_sse_events(collected)
    types = [t for t, _ in events]
    assert "planning_artifact" in types
    assert types[-1] == "message_end"


# ── Realistic SSE tests using ScriptedKaniEngine ──


async def test_scripted_engine_text_only_sse_contract(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """A text-only scripted response produces correct SSE event ordering."""
    turns = [
        ScriptedTurn(content="PlasmoDB is a genomics database for Plasmodium species."),
    ]
    with scripted_engine_factory(turns):
        result = await collect_chat_stream(
            authed_client,
            message="What is PlasmoDB?",
            site_id="plasmodb",
            timeout=30.0,
        )

    assert result.http_status == 200
    types = result.event_types
    assert types[0] == "message_start"
    assert "assistant_delta" in types
    assert "assistant_message" in types
    assert types[-1] == "message_end"

    # Deltas should come before the final message
    first_delta = types.index("assistant_delta")
    last_message = len(types) - 1 - types[::-1].index("assistant_message")
    assert first_delta < last_message


async def test_scripted_engine_with_tool_call_sse_contract(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """A scripted response with tool calls produces paired start/end events."""
    turns = [
        ScriptedTurn(
            tool_calls=[ScriptedToolCall("list_sites", {})],
        ),
        ScriptedTurn(content="There are several VEuPathDB sites available."),
    ]
    with scripted_engine_factory(turns):
        result = await collect_chat_stream(
            authed_client,
            message="What sites are available?",
            site_id="plasmodb",
            timeout=30.0,
        )

    assert result.http_status == 200
    types = result.event_types
    assert types[0] == "message_start"
    assert types[-1] == "message_end"

    # Tool call events should be paired
    assert "tool_call_start" in types
    assert "tool_call_end" in types
    tool_pairs = result.tool_calls
    assert len(tool_pairs) >= 1
    assert tool_pairs[0][0].data.get("name") == "list_sites"

    # Final assistant message should follow tool calls
    assert "assistant_message" in types
    last_tool_end = len(types) - 1 - types[::-1].index("tool_call_end")
    first_message_after = types.index("assistant_message")
    assert first_message_after > last_tool_end
