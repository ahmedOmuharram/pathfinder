"""Integration tests for the per-turn undo endpoint.

Tests the full flow:
    1. Send chat messages via POST /chat → collect SSE
    2. POST /chat/{stream_id}/undo with entryId
    3. Verify messages truncated, projection rebuilt, response correct

All tests use real Redis + real PostgreSQL. Only the LLM is mocked
(via scripted_engine_factory).
"""

import httpx
import pytest

from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedEngineFactory,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream


@pytest.mark.asyncio
async def test_chat_response_includes_entry_id(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """POST /chat response includes entryId for undo support."""
    with scripted_engine_factory([ScriptedTurn(content="Hello!")]):
        resp = await authed_client.post(
            "/api/v1/chat",
            json={"siteId": "plasmodb", "message": "hi"},
        )
    assert resp.status_code == 202
    body = resp.json()
    assert "entryId" in body
    assert isinstance(body["entryId"], str)
    assert body["entryId"] != ""


@pytest.mark.asyncio
async def test_undo_single_turn(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Undo the only turn → empty projection (0 messages)."""
    with scripted_engine_factory([ScriptedTurn(content="Response 1")]):
        result = await collect_chat_stream(
            authed_client,
            message="Turn 1",
            site_id="plasmodb",
        )
    assert result.http_status == 202
    assert result.entry_id is not None
    strategy_id = result.strategy_id
    assert strategy_id is not None

    # Undo the only turn.
    resp = await authed_client.post(
        f"/api/v1/chat/{strategy_id}/undo",
        json={"entryId": result.entry_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["messageCount"] == 0
    assert body["wdkStrategyId"] is None


@pytest.mark.asyncio
async def test_undo_second_turn_keeps_first(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Send two turns, undo the second → first turn's messages survive."""
    # Turn 1
    with scripted_engine_factory([ScriptedTurn(content="Response 1")]):
        r1 = await collect_chat_stream(
            authed_client,
            message="Turn 1",
            site_id="plasmodb",
        )
    assert r1.http_status == 202
    strategy_id = r1.strategy_id
    assert strategy_id is not None

    # Turn 2 (same strategy)
    with scripted_engine_factory([ScriptedTurn(content="Response 2")]):
        r2 = await collect_chat_stream(
            authed_client,
            message="Turn 2",
            site_id="plasmodb",
            strategy_id=strategy_id,
        )
    assert r2.http_status == 202
    assert r2.entry_id is not None

    # Undo turn 2.
    resp = await authed_client.post(
        f"/api/v1/chat/{strategy_id}/undo",
        json={"entryId": r2.entry_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Turn 1 had 1 user + 1 assistant = 2 messages.
    assert body["messageCount"] == 2


@pytest.mark.asyncio
async def test_undo_invalid_entry_id_returns_404(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Undo with a non-existent entryId returns 404."""
    with scripted_engine_factory([ScriptedTurn(content="Hello")]):
        r = await collect_chat_stream(
            authed_client,
            message="Test",
            site_id="plasmodb",
        )
    assert r.http_status == 202
    strategy_id = r.strategy_id
    assert strategy_id is not None

    resp = await authed_client.post(
        f"/api/v1/chat/{strategy_id}/undo",
        json={"entryId": "9999999999999-0"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_undo_nonexistent_stream_returns_404(
    authed_client: httpx.AsyncClient,
) -> None:
    """Undo on a stream that doesn't exist returns 404."""
    resp = await authed_client.post(
        "/api/v1/chat/00000000-0000-0000-0000-000000000000/undo",
        json={"entryId": "1234567890-0"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_undo_missing_entry_id_returns_422(
    authed_client: httpx.AsyncClient,
) -> None:
    """Undo without entryId in body returns 422."""
    resp = await authed_client.post(
        "/api/v1/chat/00000000-0000-0000-0000-000000000000/undo",
        json={},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_undo_three_turns_to_first(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Send three turns, undo from turn 2 → only turn 1 survives."""
    # Turn 1
    with scripted_engine_factory([ScriptedTurn(content="R1")]):
        r1 = await collect_chat_stream(
            authed_client, message="T1", site_id="plasmodb"
        )
    strategy_id = r1.strategy_id
    assert strategy_id is not None

    # Turn 2
    with scripted_engine_factory([ScriptedTurn(content="R2")]):
        r2 = await collect_chat_stream(
            authed_client,
            message="T2",
            site_id="plasmodb",
            strategy_id=strategy_id,
        )

    # Turn 3
    with scripted_engine_factory([ScriptedTurn(content="R3")]):
        await collect_chat_stream(
            authed_client,
            message="T3",
            site_id="plasmodb",
            strategy_id=strategy_id,
        )

    # Undo from turn 2 → turns 2 and 3 are removed.
    assert r2.entry_id is not None
    resp = await authed_client.post(
        f"/api/v1/chat/{strategy_id}/undo",
        json={"entryId": r2.entry_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Only turn 1 survives: 1 user + 1 assistant = 2 messages.
    assert body["messageCount"] == 2


@pytest.mark.asyncio
async def test_undo_is_idempotent(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Undoing with a previously-deleted entryId returns 404 (already gone)."""
    with scripted_engine_factory([ScriptedTurn(content="R1")]):
        r1 = await collect_chat_stream(
            authed_client, message="T1", site_id="plasmodb"
        )
    strategy_id = r1.strategy_id
    assert strategy_id is not None
    assert r1.entry_id is not None

    # First undo succeeds.
    resp = await authed_client.post(
        f"/api/v1/chat/{strategy_id}/undo",
        json={"entryId": r1.entry_id},
    )
    assert resp.status_code == 200

    # Second undo with same entryId → 404 (entry already deleted).
    resp = await authed_client.post(
        f"/api/v1/chat/{strategy_id}/undo",
        json={"entryId": r1.entry_id},
    )
    assert resp.status_code == 404
