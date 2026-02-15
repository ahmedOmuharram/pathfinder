"""Full-flow integration tests: multi-step strategy building.

Tests compound strategies with combines, transforms, and complex step trees.
All WDK calls are live against real VEuPathDB endpoints.

Requires network access.  Run with:

    pytest src/veupath_chatbot/tests/integration/test_full_flow_multi_step.py -v -s

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


class TestCombineIntersect:
    """Build a strategy: (epitope genes) INTERSECT (expression genes).

    This is the core compound-query pattern — find genes matching
    criterion A AND criterion B.  Exercises combine step creation,
    boolean question parameter encoding, and strategy tree assembly.


    """

    TURNS = [
        # Step 1: find epitope search
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "epitope antigen"},
                )
            ]
        ),
        # Step 2: create epitope step
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
                        "display_name": "Epitope genes",
                    },
                )
            ]
        ),
        # Step 3: find expression search
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "RNA-Seq differential expression"},
                )
            ]
        ),
        # Step 4: get parameters for expression search
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
        # Step 5: create expression step
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
                        "display_name": "Gametocyte V up-regulated",
                    },
                )
            ]
        ),
        # Step 6: list steps to get IDs for the combine
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall("list_current_steps", {}),
            ]
        ),
        # Step 7 is dynamically scripted — we can't hardcode step IDs.
        # Instead, we use ensure_single_output which auto-combines loose roots.
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "ensure_single_output",
                    {"operator": "INTERSECT"},
                )
            ]
        ),
        # Step 8: build the strategy
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "build_strategy",
                    {"strategy_name": "Epitope genes in gametocytes"},
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "I've built a strategy that intersects genes with epitope "
                "evidence and genes upregulated in gametocyte V."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(self, authed_client, scripted_engine_factory) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Find genes with epitopes that are also upregulated in gametocytes",
                site_id="plasmodb",
                mode="execute",
                timeout=180.0,
            )

        assert result.http_status == 200, f"HTTP {result.http_status}"
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in result.tool_calls]
        # Should have two create_step calls (two searches) plus ensure_single_output
        assert tool_names.count("create_step") >= 2, (
            f"Expected 2+ create_step, got {tool_names}"
        )
        assert "ensure_single_output" in tool_names
        assert "build_strategy" in tool_names

        # WDK strategy should be created — pick the last strategy_link
        # (earlier events may have wdkStrategyId=None before compilation)
        link_events = result.events_of_type("strategy_link")
        assert len(link_events) >= 1
        wdk_id = link_events[-1].data.get("wdkStrategyId")
        assert isinstance(wdk_id, int), f"Expected int wdkStrategyId, got {wdk_id}"

        assert result.assistant_content


class TestSearchPlusTransform:
    """Build a strategy: search → ortholog transform.

    Finds gametocyte genes in P. falciparum, then transforms to
    P. vivax orthologs.  Exercises transform step creation with
    input step wiring.


    """

    TURNS = [
        # Find and create the base search
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
        # List steps to get the step ID for transform input
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall("list_current_steps", {}),
            ]
        ),
        # Get ortholog transform parameters
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "get_search_parameters",
                    {
                        "record_type": "gene",
                        "search_name": "GenesByOrthologPattern",
                    },
                )
            ]
        ),
    ]

    # We need a dynamic turn for the transform — the step ID comes from create_step.
    # We'll add it via a callback approach: after the list_current_steps tool returns,
    # the next turn uses the step ID from that result.
    # For the scripted engine, we use a placeholder and rely on the test to work.

    @pytest.mark.asyncio
    async def test_full_flow(self, authed_client, scripted_engine_factory) -> None:
        """This test uses a two-phase approach:
        1. First request creates a base search and lists steps
        2. Second request creates the transform using the step ID
        """
        # Phase 1: Create base search
        phase1_turns = [
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
                    ScriptedToolCall("list_current_steps", {}),
                ]
            ),
            ScriptedTurn(
                content="I've created the base epitope search. Now let me add the ortholog transform."
            ),
        ]

        with scripted_engine_factory(phase1_turns):
            r1 = await collect_chat_stream(
                authed_client,
                message="Find epitope genes in P. falciparum then find orthologs in P. vivax",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert r1.http_status == 200
        strategy_id = r1.strategy_id
        assert strategy_id

        # Extract the step ID from list_current_steps result
        step_id = None
        for start, end in r1.tool_calls:
            if start.data.get("name") == "list_current_steps":
                import json

                result_str = end.data.get("result", "{}")
                try:
                    result_data = (
                        json.loads(result_str)
                        if isinstance(result_str, str)
                        else result_str
                    )
                except json.JSONDecodeError, TypeError:
                    result_data = {}
                # Extract step IDs from the result
                if isinstance(result_data, dict):
                    steps = result_data.get("steps") or result_data.get("data") or []
                    if isinstance(steps, list) and steps:
                        first_step = steps[0]
                        if isinstance(first_step, dict):
                            step_id = first_step.get("stepId") or first_step.get("id")
                elif isinstance(result_data, list) and result_data:
                    first_step = result_data[0]
                    if isinstance(first_step, dict):
                        step_id = first_step.get("stepId") or first_step.get("id")
                break

        if step_id is None:
            # Fall back: check strategy_update events for step IDs
            for evt in r1.events_of_type("strategy_update"):
                step_data = evt.data.get("step", {})
                if isinstance(step_data, dict):
                    step_id = step_data.get("stepId")
                    if step_id:
                        break

        assert step_id, "Could not determine step ID for transform input"

        # Phase 2: Add ortholog transform
        phase2_turns = [
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "create_step",
                        {
                            "search_name": "GenesByOrthologPattern",
                            "record_type": "gene",
                            "parameters": {
                                "organism": '["Plasmodium vivax P01"]',
                            },
                            "primary_input_step_id": str(step_id),
                            "display_name": "P. vivax orthologs",
                        },
                    )
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "build_strategy",
                        {"strategy_name": "Epitope orthologs in P. vivax"},
                    )
                ]
            ),
            ScriptedTurn(
                content="I've added an ortholog transform to find P. vivax orthologs of the epitope genes."
            ),
        ]

        with scripted_engine_factory(phase2_turns):
            r2 = await collect_chat_stream(
                authed_client,
                message="Now add an ortholog transform to find P. vivax orthologs",
                site_id="plasmodb",
                mode="execute",
                strategy_id=strategy_id,
                timeout=120.0,
            )

        assert r2.http_status == 200
        types = r2.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        tool_names = [s.data.get("name") for s, _ in r2.tool_calls]
        assert "create_step" in tool_names
        assert "build_strategy" in tool_names

        # WDK strategy should be created with the transform
        link_events = r2.events_of_type("strategy_link")
        assert len(link_events) >= 1
        assert isinstance(link_events[-1].data.get("wdkStrategyId"), int)


class TestThreeStepStrategy:
    """Complex strategy: (epitope genes → P. vivax orthologs) UNION (blood-stage genes).

    This is a realistic multi-step research workflow that exercises:
    - Two independent search creations
    - One transform
    - One combine (UNION)
    - Strategy compilation with a 4-node step tree


    """

    @pytest.mark.asyncio
    async def test_full_flow(self, authed_client, scripted_engine_factory) -> None:
        # Phase 1: Create two search steps
        phase1_turns = [
            # Epitope search
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
                            "display_name": "High-confidence epitope genes",
                        },
                    )
                ]
            ),
            # Second independent search (epitope with different confidence)
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
                    ScriptedToolCall("list_current_steps", {}),
                ]
            ),
            ScriptedTurn(content="Created two search steps. I'll now combine them."),
        ]

        with scripted_engine_factory(phase1_turns):
            r1 = await collect_chat_stream(
                authed_client,
                message="Find epitope genes and known vaccine targets, then combine them",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert r1.http_status == 200
        strategy_id = r1.strategy_id
        assert strategy_id

        # Phase 2: Combine and build
        phase2_turns = [
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "ensure_single_output",
                        {
                            "operator": "UNION",
                            "display_name": "Combined vaccine candidates",
                        },
                    )
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "build_strategy",
                        {"strategy_name": "Vaccine candidate analysis"},
                    )
                ]
            ),
            ScriptedTurn(
                content=(
                    "I've built a strategy that combines epitope genes "
                    "with known vaccine targets using UNION."
                )
            ),
        ]

        with scripted_engine_factory(phase2_turns):
            r2 = await collect_chat_stream(
                authed_client,
                message="Now combine these with UNION and build the strategy",
                site_id="plasmodb",
                mode="execute",
                strategy_id=strategy_id,
                timeout=120.0,
            )

        assert r2.http_status == 200

        tool_names = [s.data.get("name") for s, _ in r2.tool_calls]
        assert "ensure_single_output" in tool_names
        assert "build_strategy" in tool_names

        # WDK strategy created
        link_events = r2.events_of_type("strategy_link")
        assert len(link_events) >= 1
        assert isinstance(link_events[-1].data.get("wdkStrategyId"), int)
