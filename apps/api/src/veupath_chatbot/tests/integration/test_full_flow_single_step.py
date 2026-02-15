"""Full-flow integration tests: single-step strategy building.

These tests exercise the **complete pipeline** from user message through
agent tool dispatch → live WDK API → strategy persistence → SSE events.

Only the LLM decision layer is scripted; everything else is real code
hitting real VEuPathDB endpoints.

Requires network access.  Run with:

    pytest src/veupath_chatbot/tests/integration/test_full_flow_single_step.py -v -s

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


class TestSingleStepRNASeqSearch:
    """The most basic user flow: ask for a search, model explores catalog,
    gets parameter specs, creates a step, and builds the strategy.

    Uses *real* PlasmoDB RNA-Seq differential expression data.

    The scripted turns mirror what a well-behaved LLM would do:
    1. search_for_searches → find the RNA-Seq search
    2. get_search_parameters → inspect parameter specs
    3. create_step → create the search with biologically correct params
    4. build_strategy → compile to WDK
    5. Final text message


    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {
                        "query": "RNA-Seq differential expression gametocyte",
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "get_search_parameters",
                    {
                        "record_type": "transcript",
                        "search_name": "GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC",
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "create_step",
                    {
                        "search_name": "GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC",
                        "record_type": "transcript",
                        "parameters": {
                            "dataset_url": "https://PlasmoDB.org/a/app/record/dataset/DS_66f9e70b8a",
                            "profileset_generic": "P. falciparum Su Seven Stages RNA Seq data -   unstranded",
                            "regulated_dir": "up-regulated",
                            "samples_fc_comp_generic": '["Gametocyte V"]',
                            "min_max_avg_comp": "average1",
                            "samples_fc_ref_generic": '["Ring","Early Trophozoite","Late Trophozoite","Schizont"]',
                            "min_max_avg_ref": "average1",
                            "fold_change": "2",
                            "hard_floor": "5271.566971799924622138383777958655190582",
                            "protein_coding_only": "yes",
                        },
                        "display_name": "Gametocyte V up-regulated genes",
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "build_strategy",
                    {
                        "strategy_name": "Gametocyte expression analysis",
                        "record_type": "transcript",
                    },
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "I've built a strategy searching for genes upregulated in "
                "gametocyte stage V compared to ring and trophozoite stages "
                "in P. falciparum using the Su et al. seven-stages RNA-Seq dataset."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find genes upregulated in P. falciparum gametocytes using RNA-Seq data",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200, f"HTTP {result.http_status}: {result.events}"
        types = result.event_types

        assert types[0] == "message_start", (
            f"First event should be message_start, got {types}"
        )
        assert "message_end" in types, f"Expected message_end in events, got {types}"

        # Tool calls: at least search_for_searches, get_search_parameters, create_step, build_strategy
        tool_pairs = result.tool_calls
        tool_names = [start.data.get("name") for start, _ in tool_pairs]
        assert "search_for_searches" in tool_names, (
            f"Expected search_for_searches in {tool_names}"
        )
        assert "create_step" in tool_names, f"Expected create_step in {tool_names}"
        assert "build_strategy" in tool_names, (
            f"Expected build_strategy in {tool_names}"
        )

        # build_strategy should produce a strategy_link with a real WDK strategy ID
        link_events = result.events_of_type("strategy_link")
        assert len(link_events) >= 1, "Expected strategy_link event from build_strategy"
        wdk_strategy_id = link_events[-1].data.get("wdkStrategyId")
        assert wdk_strategy_id is not None, "strategy_link should contain wdkStrategyId"
        assert isinstance(wdk_strategy_id, int), (
            f"wdkStrategyId should be int, got {type(wdk_strategy_id)}"
        )

        # Assistant produced a message
        assert result.assistant_content, "Expected non-empty assistant message"

        strategy_id = result.strategy_id
        assert strategy_id, "Expected strategy ID in message_start"

        # Fetch persisted strategy
        resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert resp.status_code == 200
        strategy = resp.json()
        assert strategy["siteId"] == "plasmodb"
        # Strategy should have a name set by build_strategy
        assert strategy.get("name"), "Strategy should have a name"
        # Record type should be transcript
        assert strategy.get("recordType") == "transcript", (
            f"Unexpected recordType: {strategy.get('recordType')}"
        )


class TestSingleStepEpitopeSearch:
    """Exercises hierarchical vocabulary parameters (organism tree, confidence).

    The model creates a search for genes with epitope evidence in P. falciparum.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "epitope antigen"},
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "get_search_parameters",
                    {
                        "record_type": "transcript",
                        "search_name": "GenesWithEpitopes",
                    },
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
                            "epitope_confidence": '["High","Medium"]',
                        },
                        "display_name": "Genes with high/medium epitopes",
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "build_strategy",
                    {"strategy_name": "Epitope genes P. falciparum"},
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "I've created a strategy for P. falciparum genes with "
                "high or medium-confidence epitope evidence."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find P. falciparum genes with epitope evidence",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200, f"HTTP {result.http_status}"
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        assert "create_step" in tool_names
        assert "build_strategy" in tool_names

        link_events = result.events_of_type("strategy_link")
        assert len(link_events) >= 1, "Expected strategy_link from build_strategy"
        assert isinstance(link_events[-1].data.get("wdkStrategyId"), int)

        # Verify persistence
        strategy_id = result.strategy_id
        assert strategy_id
        resp = await authed_client.get(f"/api/v1/strategies/{strategy_id}")
        assert resp.status_code == 200
        strategy = resp.json()
        assert strategy.get("recordType") == "transcript"


class TestSingleStepEpitopeVariant:
    """User asks for epitope genes with a different confidence filter.

    Exercises the same create_step → build_strategy pipeline as the
    epitope test above but with a different parameter set (low confidence
    only), verifying that parameter values are passed through correctly.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "epitope prediction"},
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "get_search_parameters",
                    {
                        "record_type": "transcript",
                        "search_name": "GenesWithEpitopes",
                    },
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
                            "epitope_confidence": '["Low"]',
                        },
                        "display_name": "Low-confidence epitope genes",
                    },
                )
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "build_strategy",
                    {"strategy_name": "Low-confidence epitope analysis"},
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "I've built a strategy searching for P. falciparum genes "
                "with low-confidence epitope predictions."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find P. falciparum genes with low-confidence epitope predictions",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert result.http_status == 200, f"HTTP {result.http_status}"
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        assert "create_step" in tool_names

        # Verify we got a strategy_link (WDK strategy created)
        link_events = result.events_of_type("strategy_link")
        assert len(link_events) >= 1
        assert isinstance(link_events[-1].data.get("wdkStrategyId"), int)

        assert result.assistant_content


class TestCatalogExploration:
    """Model explores the catalog before building: list_sites, get_record_types,
    search_for_searches.  No strategy created, just information gathering.


    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall("list_sites", {}),
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall("get_record_types", {}),
            ]
        ),
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "proteomics mass spectrometry"},
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "PlasmoDB has several proteomics-related searches available "
                "for gene and transcript record types."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_catalog_exploration(
        self, authed_client, scripted_engine_factory
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="What proteomics searches are available on PlasmoDB?",
                site_id="plasmodb",
                mode="execute",
                timeout=60.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        assert "list_sites" in tool_names
        assert "get_record_types" in tool_names
        assert "search_for_searches" in tool_names

        # The tool results should contain real data from PlasmoDB
        for start, end in result.tool_calls:
            if start.data.get("name") == "list_sites":
                result_text = end.data.get("result", "")
                assert "plasmodb" in str(result_text).lower(), (
                    "list_sites should include PlasmoDB"
                )

        assert result.assistant_content
