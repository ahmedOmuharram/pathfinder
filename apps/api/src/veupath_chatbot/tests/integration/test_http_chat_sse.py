import json

import httpx
import pytest

from veupath_chatbot.platform.types import JSONObject


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
        "mode": "execute",
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


async def test_plan_stream_sse_emits_artifact_and_executor_request_with_mock_provider(
    authed_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATHFINDER_CHAT_PROVIDER", "mock")

    payload = {
        "siteId": "plasmodb",
        "message": "please build this in executor",
        "mode": "plan",
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

    assert types[0] == "message_start"
    assert "assistant_delta" in types
    assert "assistant_message" in types
    assert "planning_artifact" in types
    assert "executor_build_request" in types
    assert types[-1] == "message_end"

    assert types.index("planning_artifact") < types.index("executor_build_request")


async def test_execute_stream_can_emit_planning_artifact_with_mock_provider(
    authed_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATHFINDER_CHAT_PROVIDER", "mock")

    payload = {
        "siteId": "plasmodb",
        "message": "please emit artifact",
        "mode": "execute",
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
