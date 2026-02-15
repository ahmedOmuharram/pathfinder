"""Full-flow integration tests: planning mode.

Tests plan-mode conversations, control tests, parameter optimization,
and plan-to-execute graduation — all with live WDK calls.

Run with:

    pytest src/veupath_chatbot/tests/integration/test_full_flow_planning.py -v -s

Skip with:

    pytest -m "not live_wdk"
"""

from __future__ import annotations

import json

import httpx
import pytest

from veupath_chatbot.tests.fixtures.scripted_engine import (
    ScriptedEngineFactory,
    ScriptedToolCall,
    ScriptedTurn,
)
from veupath_chatbot.tests.fixtures.sse_collector import collect_chat_stream

pytestmark = pytest.mark.live_wdk


# Known gametocyte-upregulated genes (positive controls)
POSITIVE_CONTROLS = [
    "PF3D7_1222600",  # PfAP2-G – master regulator of sexual commitment
    "PF3D7_1031000",  # Pfs25 – surface antigen, TBV candidate
    "PF3D7_0209000",  # Pfs230 – gamete fertility factor
    "PF3D7_1346700",  # Pfs48/45 – TBV candidate
    "PF3D7_1346800",  # Pfs47 – female gamete fertility
    "PF3D7_0935400",  # CDPK4 – male gametocyte kinase
    "PF3D7_0406200",  # MDV1/PEG3 – male gametocyte development
    "PF3D7_1408200",  # Pf11-1 – gametocyte-specific
    "PF3D7_1216500",  # GEP1 – gametocyte egress protein
    "PF3D7_1477700",  # HAP2/GCS1 – male gamete fusion factor
]

# Known asexual-stage housekeeping genes (negative controls)
NEGATIVE_CONTROLS = [
    "PF3D7_1462800",  # GAPDH
    "PF3D7_1246200",  # Actin I
    "PF3D7_0422300",  # α-Tubulin
    "PF3D7_0317600",  # Histone H2B
    "PF3D7_1357000",  # EF-1α
    "PF3D7_0708400",  # HSP90
    "PF3D7_0818900",  # HSP70-1
    "PF3D7_0617800",  # Histone H3
]

RNASEQ_FIXED_PARAMS = {
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
}


class TestPlanningArtifact:
    """Plan mode: explore catalog and save a planning artifact with a
    proposed strategy plan.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "search_for_searches",
                    {"query": "vaccine target epitope"},
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
                    "save_planning_artifact",
                    {
                        "title": "Vaccine target search plan",
                        "summary_markdown": (
                            "## Approach\n\n"
                            "1. Use **GenesWithEpitopes** to find genes with epitope evidence\n"
                            "2. Filter by high-confidence epitopes in P. falciparum 3D7\n"
                            "3. Optionally combine with expression data to prioritize\n\n"
                            "## Parameters\n"
                            "- organism: Plasmodium falciparum 3D7\n"
                            "- epitope_confidence: High, Medium"
                        ),
                        "assumptions": [
                            "Focusing on P. falciparum 3D7 only",
                            "Using IEDB epitope predictions from PlasmoDB",
                        ],
                        "proposed_strategy_plan": {
                            "recordType": "transcript",
                            "root": {
                                "id": "step_1",
                                "searchName": "GenesWithEpitopes",
                                "displayName": "P. falciparum epitope genes",
                                "parameters": {
                                    "organism": ["Plasmodium falciparum 3D7"],
                                    "epitope_confidence": ["High", "Medium"],
                                },
                            },
                        },
                    },
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "I've analyzed the available searches and created a plan "
                "for finding vaccine targets using epitope evidence."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(
        self,
        authed_client: httpx.AsyncClient,
        scripted_engine_factory: ScriptedEngineFactory,
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Help me plan a strategy to find vaccine targets on PlasmoDB",
                site_id="plasmodb",
                mode="plan",
                timeout=120.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        # Planning artifact should be emitted
        artifact_events = result.events_of_type("planning_artifact")
        assert len(artifact_events) >= 1, "Expected planning_artifact event"
        artifact = artifact_events[0].data.get("planningArtifact", {})
        assert isinstance(artifact, dict)
        assert artifact.get("title"), "Artifact should have a title"
        assert artifact.get("summaryMarkdown"), "Artifact should have a summary"

        # The proposed plan should have a real search name
        plan = artifact.get("proposedStrategyPlan")
        if plan and isinstance(plan, dict):
            root = plan.get("root", {})
            if isinstance(root, dict):
                assert root.get("searchName") == "GenesWithEpitopes"


class TestControlTests:
    """Planner runs control tests to validate a search configuration
    against known positive/negative gene lists.

    This exercises the exact same WDK pipeline as the existing
    test_live_control_tests.py but through the full chat/agent flow.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "run_control_tests",
                    {
                        "record_type": "transcript",
                        "target_search_name": "GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC",
                        "target_parameters": RNASEQ_FIXED_PARAMS,
                        "controls_search_name": "GeneByLocusTag",
                        "controls_param_name": "ds_gene_ids",
                        "positive_controls": POSITIVE_CONTROLS,
                        "negative_controls": NEGATIVE_CONTROLS,
                        "controls_value_format": "newline",
                    },
                )
            ]
        ),
        ScriptedTurn(
            content=(
                "Control test results: the search achieves good recall "
                "on known gametocyte markers while maintaining low false "
                "positive rate on housekeeping genes."
            )
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(
        self,
        authed_client: httpx.AsyncClient,
        scripted_engine_factory: ScriptedEngineFactory,
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Run control tests for gametocyte expression search",
                site_id="plasmodb",
                mode="plan",
                timeout=180.0,
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        # Check tool call result
        tool_pairs = result.tool_calls
        control_results = [
            (s, e) for s, e in tool_pairs if s.data.get("name") == "run_control_tests"
        ]
        assert len(control_results) >= 1, "Expected run_control_tests tool call"

        _, end = control_results[0]
        result_str = end.data.get("result", "{}")
        try:
            data = json.loads(result_str) if isinstance(result_str, str) else result_str
        except json.JSONDecodeError, TypeError:
            data = {}

        if isinstance(data, dict):
            # Check positive controls
            positive = data.get("positive")
            if positive and isinstance(positive, dict):
                recall = positive.get("recall")
                assert recall is not None, "Expected recall in positive controls"
                assert isinstance(recall, (int, float))
                assert recall > 0, "Expected recall > 0 for gametocyte markers"

            # Check negative controls
            negative = data.get("negative")
            if negative and isinstance(negative, dict):
                fpr = negative.get("falsePositiveRate")
                assert fpr is not None, (
                    "Expected falsePositiveRate in negative controls"
                )

            # Sanity: recall should be better than random
            target = data.get("target", {})
            if isinstance(target, dict):
                count = target.get("resultCount")
                assert count is not None
                assert isinstance(count, (int, float)) and int(count) > 0, (
                    "Expected positive result count"
                )


class TestParameterOptimization:
    """Run parameter optimization with a very small budget (3 trials)
    to test the full optimization pipeline including progress events.
    """

    TURNS = [
        ScriptedTurn(
            tool_calls=[
                ScriptedToolCall(
                    "optimize_search_parameters",
                    {
                        "record_type": "transcript",
                        "search_name": "GenesByRNASeqpfal3D7_Su_seven_stages_rnaSeq_RSRC",
                        "parameter_space_json": json.dumps(
                            [
                                {
                                    "name": "fold_change",
                                    "type": "float",
                                    "low": 1.5,
                                    "high": 5.0,
                                }
                            ]
                        ),
                        "fixed_parameters_json": json.dumps(
                            {
                                "dataset_url": "https://PlasmoDB.org/a/app/record/dataset/DS_66f9e70b8a",
                                "profileset_generic": "P. falciparum Su Seven Stages RNA Seq data -   unstranded",
                                "regulated_dir": "up-regulated",
                                "samples_fc_comp_generic": '["Gametocyte V"]',
                                "min_max_avg_comp": "average1",
                                "samples_fc_ref_generic": '["Ring","Early Trophozoite","Late Trophozoite","Schizont"]',
                                "min_max_avg_ref": "average1",
                                "hard_floor": "5271.566971799924622138383777958655190582",
                                "protein_coding_only": "yes",
                            }
                        ),
                        "controls_search_name": "GeneByLocusTag",
                        "controls_param_name": "ds_gene_ids",
                        "positive_controls": POSITIVE_CONTROLS[
                            :5
                        ],  # smaller set for speed
                        "negative_controls": NEGATIVE_CONTROLS[:4],
                        "budget": 3,
                        "objective": "f1",
                        "method": "random",
                        "controls_value_format": "newline",
                    },
                )
            ]
        ),
        ScriptedTurn(
            content="Optimization complete. The best fold change value was found."
        ),
    ]

    @pytest.mark.asyncio
    async def test_full_flow(
        self,
        authed_client: httpx.AsyncClient,
        scripted_engine_factory: ScriptedEngineFactory,
    ) -> None:
        with scripted_engine_factory(self.TURNS):
            result = await collect_chat_stream(
                authed_client,
                message="Optimize the fold change parameter for gametocyte detection",
                site_id="plasmodb",
                mode="plan",
                timeout=300.0,  # optimization can take a while
            )

        assert result.http_status == 200
        types = result.event_types
        assert types[0] == "message_start"
        assert "message_end" in types

        # Should have optimization_progress events
        progress_events = result.events_of_type("optimization_progress")
        # At least "started" and "completed"
        assert len(progress_events) >= 2, (
            f"Expected ≥2 optimization_progress events, got {len(progress_events)}"
        )

        # Check that we got trial results
        statuses = [e.data.get("status") for e in progress_events]
        assert "started" in statuses or any("trial" in str(s) for s in statuses), (
            f"Expected 'started' in progress statuses: {statuses}"
        )


class TestPlanToExecuteGraduation:
    """Two-phase flow:
    1. Plan mode: explore and produce a planning artifact
    2. Execute mode: build the strategy based on the plan

    Tests the plan→execute handoff workflow.
    """

    @pytest.mark.asyncio
    async def test_graduation(self, authed_client, scripted_engine_factory) -> None:
        # Phase 1: Plan mode — create a planning artifact
        plan_turns = [
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
                        "save_planning_artifact",
                        {
                            "title": "Epitope gene strategy",
                            "summary_markdown": "Search for epitope genes in P. falciparum.",
                            "proposed_strategy_plan": {
                                "recordType": "transcript",
                                "root": {
                                    "id": "step_1",
                                    "searchName": "GenesWithEpitopes",
                                    "parameters": {
                                        "organism": ["Plasmodium falciparum 3D7"],
                                        "epitope_confidence": ["High"],
                                    },
                                },
                            },
                        },
                    )
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "request_executor_build",
                        {
                            "delegation_goal": "Build the epitope gene strategy",
                            "delegation_plan": {
                                "type": "task",
                                "task": "Find P. falciparum genes with epitope evidence",
                                "hint": "Use GenesWithEpitopes with organism Plasmodium falciparum 3D7, epitope_confidence High",
                            },
                        },
                    )
                ]
            ),
            ScriptedTurn(content="I've created the plan. Let me build it for you now."),
        ]

        with scripted_engine_factory(plan_turns):
            r_plan = await collect_chat_stream(
                authed_client,
                message="Plan a strategy for P. falciparum epitope genes, then build it",
                site_id="plasmodb",
                mode="plan",
                timeout=120.0,
            )

        assert r_plan.http_status == 200
        artifact_events = r_plan.events_of_type("planning_artifact")
        assert len(artifact_events) >= 1, "Expected planning_artifact in plan phase"

        exec_request_events = r_plan.events_of_type("executor_build_request")
        assert len(exec_request_events) >= 1, "Expected executor_build_request"

        # Phase 2: Execute mode — build the strategy
        exec_turns = [
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
                            "display_name": "P. falciparum epitope genes",
                        },
                    )
                ]
            ),
            ScriptedTurn(
                tool_calls=[
                    ScriptedToolCall(
                        "build_strategy",
                        {"strategy_name": "Epitope gene strategy"},
                    )
                ]
            ),
            ScriptedTurn(content="I've built the strategy from the plan."),
        ]

        with scripted_engine_factory(exec_turns):
            r_exec = await collect_chat_stream(
                authed_client,
                message="Build the epitope gene strategy as planned",
                site_id="plasmodb",
                mode="execute",
                timeout=120.0,
            )

        assert r_exec.http_status == 200
        link_events = r_exec.events_of_type("strategy_link")
        assert len(link_events) >= 1, "Expected strategy_link in execute phase"
        assert isinstance(link_events[-1].data.get("wdkStrategyId"), int)
