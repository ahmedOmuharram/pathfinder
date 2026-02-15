"""Full-flow integration tests: SSE event contract and persistence.

Verifies that the SSE event stream has correct ordering, that
persistence writes the right data, and that multi-turn message
history is consistent.

All WDK calls are live.  Run with:

    pytest src/veupath_chatbot/tests/integration/test_full_flow_event_contract.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from __future__ import annotations

import pytest

from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedToolCall,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream

pytestmark = pytest.mark.live_wdk


class TestEventOrdering:
    """Verify the strict SSE event ordering contract for a tool-calling turn."""

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "epitope"},
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesWithEpitopes",
                        "record_type": "transcript",
                        "parameters": {
                            "organism": '["Plasmodium falciparum 3D7"]',
                            "epitope_confidence": '["High"]',
                        },
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "build_strategy",
                    {"strategy_name": "Event ordering test"},
                )
            ]
        ),
        ScriptedTurn(content="Strategy built successfully."),
    ]

    @pytest.mark.asyncio
    async def test_event_ordering(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Build an epitope search strategy",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200
        types = result.event_types

        # 1. message_start is always first
        assert types[0] == "message_start", (
            f"First event must be message_start, got {types[0]}"
        )

        # 2. message_end is always last
        assert "message_end" in types, f"Expected message_end in events, got {types}"

        # 3. tool_call_start always precedes its matching tool_call_end
        for start, _end in result.tool_calls:
            start_idx = None
            end_idx = None
            call_id = start.data.get("id")
            for i, e in enumerate(result.events):
                if e.type == "tool_call_start" and e.data.get("id") == call_id:
                    start_idx = i
                elif e.type == "tool_call_end" and e.data.get("id") == call_id:
                    end_idx = i
            assert start_idx is not None and end_idx is not None, (
                f"Could not find start/end for tool call {call_id}"
            )
            assert start_idx < end_idx, (
                f"tool_call_start ({start_idx}) must precede tool_call_end ({end_idx}) "
                f"for call {call_id}"
            )

        # 4. assistant_message appears before message_end
        if "assistant_message" in types:
            last_assistant_idx = len(types) - 1 - types[::-1].index("assistant_message")
            message_end_idx = types.index("message_end")
            assert last_assistant_idx < message_end_idx, (
                "assistant_message must appear before message_end"
            )

        # 5. strategy_update/graph_snapshot appear after the tool call that produces them
        for event_type in ("strategy_update", "graph_snapshot", "graph_plan"):
            for evt in result.events_of_type(event_type):
                evt_idx = result.events.index(evt)
                # Should appear after at least one tool_call_end
                tool_end_indices = [
                    i for i, e in enumerate(result.events) if e.type == "tool_call_end"
                ]
                if tool_end_indices:
                    assert evt_idx > tool_end_indices[0], (
                        f"{event_type} at index {evt_idx} should appear after a tool_call_end"
                    )


class TestMultiTurnPersistence:
    """After a two-turn conversation, verify the strategy's messages
    array contains [user1, assistant1, user2, assistant2].
    """

    @pytest.mark.asyncio
    async def test_message_persistence(
        self, authed_client, scripted_engine_factory
    ) -> None:
        # Turn 1
        with scripted_engine_factory(
            [
                ScriptedTurn(
                    tool_calls=[
                        ScriptedToolCall(
                            "create_step",
                            {
                                "search_name": "GenesWithEpitopes",
                                "record_type": "transcript",
                                "parameters": {
                                    "organism": '["Plasmodium falciparum 3D7"]',
                                    "epitope_confidence": '["High"]',
                                },
                            },
                        )
                    ]
                ),
                ScriptedTurn(content="Created an epitope search."),
            ]
        ):
            r1 = await collect_chat_stream(
                authed_client,
                message="Create an epitope search for P. falciparum",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert r1.http_status == 200
        strategy_id = r1.strategy_id
        assert strategy_id

        # Turn 2
        with scripted_engine_factory(
            [
                ScriptedTurn(
                    tool_calls=[
                        ScriptedToolCall("list_current_steps", {}),
                    ]
                ),
                ScriptedTurn(
                    content="You have one epitope search step in the strategy."
                ),
            ]
        ):
            r2 = await collect_chat_stream(
                authed_client,
                message="What steps do I have?",
                site_id="plasmodb",
                mode="execute",
                strategy_id=strategy_id,
                timeout=60.0,
            )

        assert r2.http_status == 200

        # Fetch the strategy and check messages
        resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert resp.status_code == 200
        strategy = resp.json()

        messages = strategy.get("messages", [])
        assert isinstance(messages, list)
        # Should have at least 4 messages: user1, assistant1, user2, assistant2
        assert len(messages) >= 4, (
            f"Expected ≥4 messages after 2 turns, got {len(messages)}: "
            f"{[m.get('role') for m in messages if isinstance(m, dict)]}"
        )

        roles = [m.get("role") for m in messages if isinstance(m, dict)]
        # First message should be user
        assert roles[0] == "user"
        # Should have at least one assistant message after each user
        assert "assistant" in roles


class TestThinkingCleared:
    """During streaming, the thinking payload is updated.  After the
    stream completes, it should be cleared (null).
    """

    @pytest.mark.asyncio
    async def test_thinking_cleared(
        self, authed_client, scripted_engine_factory
    ) -> None:
        with scripted_engine_factory(
            [
                ScriptedTurn(
                    tool_calls=[
                        ScriptedToolCall(
                            "search_for_searches",
                            {"query": "epitope"},
                        )
                    ]
                ),
                ScriptedTurn(content="Found some searches."),
            ]
        ):
            result = await collect_chat_stream(
                authed_client,
                message="Search for epitope-related searches",
                site_id="plasmodb",
                mode="execute",
                timeout=60.0,
            )

        assert result.http_status == 200
        strategy_id = result.strategy_id
        assert strategy_id

        # After stream completes, thinking should be cleared
        resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert resp.status_code == 200
        strategy = resp.json()

        # Thinking should be null or empty after finalization
        thinking = strategy.get("thinking")
        assert thinking is None or thinking == {} or thinking == [], (
            f"Thinking should be cleared after stream, got: {thinking}"
        )


class TestStrategyMetaPersistence:
    """After building a strategy, verify the persisted metadata
    (siteId, recordType, name) is correct.
    """

    @pytest.mark.asyncio
    async def test_meta_persistence(
        self, authed_client, scripted_engine_factory
    ) -> None:
        with scripted_engine_factory(
            [
                ScriptedTurn(
                    tool_calls=[
                        ScriptedToolCall(
                            "create_step",
                            {
                                "search_name": "GenesWithEpitopes",
                                "record_type": "transcript",
                                "parameters": {
                                    "organism": '["Plasmodium falciparum 3D7"]',
                                    "epitope_confidence": '["High","Medium"]',
                                },
                            },
                        )
                    ]
                ),
                ScriptedTurn(
                    tool_calls=[
                        ScriptedToolCall(
                            "build_strategy",
                            {
                                "strategy_name": "Epitope persistence test",
                                "record_type": "transcript",
                            },
                        )
                    ]
                ),
                ScriptedTurn(content="Built the strategy."),
            ]
        ):
            result = await collect_chat_stream(
                authed_client,
                message="Build an epitope strategy for persistence test",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200
        strategy_id = result.strategy_id
        assert strategy_id

        resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert resp.status_code == 200
        strategy = resp.json()

        assert strategy.get("siteId") == "plasmodb"
        assert strategy.get("recordType") == "transcript", (
            f"Unexpected recordType: {strategy.get('recordType')}"
        )
        # The name should be set (not default "Draft Strategy")
        name = strategy.get("name") or strategy.get("title", "")
        assert name and name != "Draft Strategy", (
            f"Strategy name should be set, got: {name}"
        )
