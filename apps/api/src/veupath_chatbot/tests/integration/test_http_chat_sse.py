"""Integration tests for the chat SSE pipeline (CQRS pattern).

Tests the full flow:
    POST /chat → 202 + operationId → GET /operations/{id}/subscribe → SSE

All tests use the CQRS fire-and-forget pattern: the chat endpoint accepts
the request and returns immediately; events are consumed from a Redis-backed
SSE subscription endpoint.
"""

import httpx
import pytest

from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedEngineFactory,
    ScriptedToolCall,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream

# ── Scripted-engine tests (realistic SSE contract) ──────────────────


@pytest.mark.asyncio
async def test_text_only_sse_contract(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """A text-only response produces correct SSE event ordering."""
    with scripted_engine_factory(
        [
            ScriptedTurn(
                content="PlasmoDB is a genomics database for Plasmodium species."
            )
        ]
    ):
        result = await collect_chat_stream(
            authed_client,
            message="What is PlasmoDB?",
            site_id="plasmodb",
            request_timeout=30.0,
        )

    assert result.http_status == 202
    types = result.event_types

    # Core events present.
    assert "message_start" in types
    assert "assistant_delta" in types
    assert "assistant_message" in types
    assert types[-1] == "message_end"

    # Deltas come before the final assistant_message.
    first_delta = types.index("assistant_delta")
    last_message = len(types) - 1 - types[::-1].index("assistant_message")
    assert first_delta < last_message


@pytest.mark.asyncio
async def test_tool_call_sse_contract(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Tool calls produce paired start/end events in the SSE stream."""
    turns = [
        ScriptedTurn(tool_calls=[ScriptedToolCall("list_sites", {})]),
        ScriptedTurn(content="There are several VEuPathDB sites available."),
    ]
    with scripted_engine_factory(turns):
        result = await collect_chat_stream(
            authed_client,
            message="What sites are available?",
            site_id="plasmodb",
            request_timeout=30.0,
        )

    assert result.http_status == 202
    types = result.event_types

    assert "message_start" in types
    assert types[-1] == "message_end"

    # Tool calls are paired.
    assert "tool_call_start" in types
    assert "tool_call_end" in types
    tool_pairs = result.tool_calls
    assert len(tool_pairs) >= 1
    assert tool_pairs[0][0].data.get("name") == "list_sites"

    # assistant_message follows the last tool_call_end.
    assert "assistant_message" in types
    last_tool_end = len(types) - 1 - types[::-1].index("tool_call_end")
    first_message = types.index("assistant_message")
    assert first_message > last_tool_end


@pytest.mark.asyncio
async def test_multi_tool_sse_contract(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """Multiple sequential tool calls each produce paired events."""
    turns = [
        ScriptedTurn(
            tool_calls=[ScriptedToolCall("search_for_searches", {"query": "gene"})],
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesByTaxon",
                        "record_type": "transcript",
                        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                    },
                )
            ],
        ),
        ScriptedTurn(content="Created a gene search step."),
    ]
    with scripted_engine_factory(turns):
        result = await collect_chat_stream(
            authed_client,
            message="Find genes in P. falciparum",
            site_id="plasmodb",
            request_timeout=60.0,
        )

    assert result.http_status == 202
    types = result.event_types

    assert "message_start" in types
    assert types[-1] == "message_end"

    # Should have at least 2 tool call pairs.
    tool_pairs = result.tool_calls
    assert len(tool_pairs) >= 2
    tool_names = [pair[0].data.get("name") for pair in tool_pairs]
    assert "search_for_searches" in tool_names
    assert "create_step" in tool_names


@pytest.mark.asyncio
async def test_strategy_id_in_message_start(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """The message_start event includes a strategy ID for frontend routing."""
    with scripted_engine_factory([ScriptedTurn(content="Here is some info.")]):
        result = await collect_chat_stream(
            authed_client,
            message="Tell me something",
            site_id="plasmodb",
            request_timeout=30.0,
        )

    assert result.http_status == 202
    assert result.strategy_id is not None
    assert len(result.strategy_id) > 0


@pytest.mark.asyncio
async def test_cqrs_returns_202_with_operation_id(
    authed_client: httpx.AsyncClient,
    scripted_engine_factory: ScriptedEngineFactory,
) -> None:
    """POST /chat returns 202 Accepted with an operationId."""
    with scripted_engine_factory([ScriptedTurn(content="OK")]):
        resp = await authed_client.post(
            "/api/v1/chat",
            json={"siteId": "plasmodb", "message": "hello"},
            timeout=10.0,
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "operationId" in body
    assert body["operationId"].startswith("op_")


@pytest.mark.asyncio
async def test_unauthenticated_chat_rejected(
    client: httpx.AsyncClient,
) -> None:
    """POST /chat without auth cookie is rejected."""
    resp = await client.post(
        "/api/v1/chat",
        json={"siteId": "plasmodb", "message": "hello"},
        timeout=10.0,
    )
    assert resp.status_code in (401, 403)
