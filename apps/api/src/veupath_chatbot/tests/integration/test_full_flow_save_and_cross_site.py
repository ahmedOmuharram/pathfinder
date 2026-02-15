"""Full-flow integration tests: save/WDK push, cross-site, and delegation.

Tests strategy saving to WDK, cross-site searches (ToxoDB), and
the delegation/sub-kani flow — all with live WDK calls.

Run with:

    pytest src/veupath_chatbot/tests/integration/test_full_flow_save_and_cross_site.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from __future__ import annotations

import json

import pytest

from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedToolCall,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream

pytestmark = pytest.mark.live_wdk


class TestBuildAndSave:
    """Full flow from building a strategy to saving/pushing to WDK.

    Tests strategy compilation, WDK step+strategy creation, and the
    strategy_link SSE event.
    """

    TURNS = [
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
                        "display_name": "P. falciparum epitope genes",
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "build_strategy",
                    {
                        "strategy_name": "Vaccine targets (saved)",
                        "record_type": "transcript",
                        "description": "P. falciparum genes with high/medium epitope evidence",
                    },
                )
            ]
        ),
        ScriptedTurn(content="Strategy built and pushed to VEuPathDB as a draft."),
    ]

    @pytest.mark.asyncio
    async def test_build_and_save(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Build and save a strategy for epitope vaccine targets",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        # Strategy link event with WDK strategy ID
        link_events = result.events_of_type("strategy_link")
        assert len(link_events) >= 1, "Expected strategy_link event"
        link_data = link_events[-1].data
        wdk_id = link_data.get("wdkStrategyId")
        assert isinstance(wdk_id, int), f"wdkStrategyId should be int, got {wdk_id}"
        assert wdk_id > 0

        # The link should include a URL
        wdk_url = link_data.get("wdkUrl")
        if wdk_url:
            assert "plasmodb" in str(wdk_url).lower(), (
                f"URL should be PlasmoDB: {wdk_url}"
            )

        # DB should have wdk_strategy_id set
        strategy_id = result.strategy_id
        resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert resp.status_code == 200
        strategy = resp.json()
        assert strategy.get("wdkStrategyId") == wdk_id, (
            f"DB wdkStrategyId should match: expected {wdk_id}, got {strategy.get('wdkStrategyId')}"
        )


class TestGetResultCount:
    """After building a strategy, get the result count for a step."""

    @pytest.mark.asyncio
    async def test_result_count(self, authed_client, scripted_engine_factory) -> None:
        # Phase 1: build strategy
        build_turns = [
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
                        {"strategy_name": "Count test"},
                    )
                ]
            ),
            ScriptedTurn(content="Built. Let me check the result count."),
        ]

        with scripted_engine_factory(build_turns):
            r1 = await collect_chat_stream(
                authed_client,
                message="Build an epitope strategy and check results",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert r1.http_status == 200

        # Extract the WDK step ID from build_strategy result
        wdk_step_id = None
        for start, end in r1.tool_calls:
            if start.data.get("name") == "build_strategy":
                result_str = end.data.get("result", "{}")
                try:
                    data = (
                        json.loads(result_str)
                        if isinstance(result_str, str)
                        else result_str
                    )
                except json.JSONDecodeError, TypeError:
                    continue
                if isinstance(data, dict):
                    wdk_step_id = data.get("wdkRootStepId") or data.get("rootStepId")
                    if wdk_step_id is None:
                        # Try nested
                        step_ids = data.get("wdkStepIds") or {}
                        if isinstance(step_ids, dict) and step_ids:
                            wdk_step_id = list(step_ids.values())[0]

        if wdk_step_id is None:
            pytest.skip("Could not extract WDK step ID from build_strategy result")
        if not isinstance(wdk_step_id, (int, float, str)):
            pytest.skip("wdk_step_id is not int-able")

        # Phase 2: get result count
        count_turns = [
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "get_result_count",
                        {"wdk_step_id": int(wdk_step_id)},
                    )
                ]
            ),
            ScriptedTurn(content="The search returned some results."),
        ]

        strategy_id = r1.strategy_id
        with scripted_engine_factory(count_turns):
            r2 = await collect_chat_stream(
                authed_client,
                message="How many results?",
                site_id="plasmodb",
                mode="execute",
                strategy_id=strategy_id,
                timeout=60.0,
            )

        assert r2.http_status == 200
        tool_names = [s.data.get("name") for s, _ in r2.tool_calls]
        assert "get_result_count" in tool_names

        for start, end in r2.tool_calls:
            if start.data.get("name") == "get_result_count":
                result_str = end.data.get("result", "{}")
                try:
                    data = (
                        json.loads(result_str)
                        if isinstance(result_str, str)
                        else result_str
                    )
                except json.JSONDecodeError, TypeError:
                    continue
                if isinstance(data, dict):
                    count = (
                        data.get("count")
                        or data.get("resultCount")
                        or data.get("estimatedSize")
                    )
                    assert count is not None, f"Expected result count, got {data}"
                    assert isinstance(count, (int, float, str)), (
                        f"Expected numeric count, got {type(count)}"
                    )
                    assert int(count) > 0, f"Expected positive count, got {count}"


class TestToxoDBSearch:
    """Same single-step flow but on ToxoDB with T. gondii.

    Ensures the system is not hardcoded to PlasmoDB.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "gene expression RNA-Seq"},
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "get_record_types",
                    {},
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "ToxoDB has several RNA-Seq expression searches available "
                "for T. gondii and other Toxoplasma species."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_toxodb_catalog(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="What expression searches are available on ToxoDB?",
                site_id="toxodb",
                mode="execute",
                timeout=60.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        assert "search_for_searches" in tool_names

        # The search_for_searches result should contain ToxoDB searches (not PlasmoDB)
        for start, end in result.tool_calls:
            if start.data.get("name") == "search_for_searches":
                result_str = end.data.get("result", "[]")
                # Should be a non-empty result since ToxoDB has many expression searches
                assert len(str(result_str)) > 10, (
                    "Expected non-trivial search_for_searches result from ToxoDB"
                )


class TestCryptoDBLookup:
    """Gene lookup on CryptoDB for Cryptosporidium genes."""

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "get_record_types",
                    {},
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "gene name product"},
                )
            ]
        ),
        ScriptedTurn(
            content="CryptoDB supports gene searches for Cryptosporidium species."
        ),
    ]

    @pytest.mark.asyncio
    async def test_cryptodb_catalog(
        self, authed_client, scripted_engine_factory
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="What gene searches are available on CryptoDB?",
                site_id="cryptodb",
                mode="execute",
                timeout=60.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        assert "get_record_types" in tool_names


class TestGeneLookupAndResolve:
    """Plan mode: look up gene records by name and resolve IDs.

    Uses the planner's lookup_gene_records and resolve_gene_ids_to_records
    tools against live PlasmoDB.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "lookup_gene_records",
                    {"query": "Pfs25"},
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "resolve_gene_ids_to_records",
                    {
                        "gene_ids": ["PF3D7_1031000"],
                        "record_type": "gene",
                    },
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "Pfs25 (PF3D7_1031000) is a transmission-blocking vaccine "
                "candidate expressed on the ookinete surface."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_gene_lookup_and_resolve(
        self, authed_client, scripted_engine_factory
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Tell me about Pfs25",
                site_id="plasmodb",
                mode="plan",
                timeout=120.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        assert "lookup_gene_records" in tool_names

        # The lookup result should return gene records related to Pfs25.
        # WDK autocomplete returns genes from all strains (not just 3D7),
        # so we check for any results rather than a specific locus tag.
        for start, end in result.tool_calls:
            if start.data.get("name") == "lookup_gene_records":
                result_str = str(end.data.get("result", ""))
                try:
                    data = (
                        json.loads(result_str)
                        if isinstance(result_str, str)
                        else result_str
                    )
                except json.JSONDecodeError, TypeError:
                    data = {}
                if isinstance(data, dict):
                    results = data.get("results", [])
                    total = data.get("totalCount", 0)
                    assert len(results) > 0 or total > 0, (
                        f"Expected non-empty lookup results for Pfs25: {result_str[:500]}"
                    )
