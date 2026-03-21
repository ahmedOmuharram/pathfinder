"""Unit tests for step count optimizations.

Tests:
1. ``derive_steps_from_plan`` reads stored ``stepCounts`` from plan metadata
2. ``_build_snapshot_from_wdk`` extracts estimatedSize into a step counts dict
3. ``compute_step_counts_for_plan`` uses anonymous reports for leaf-only strategies

Search names verified against live PlasmoDB API (2026-03-10):
- GenesByTaxon: transcript record type
- GenesByLocation: transcript record type
- boolean_question_TranscriptRecordClasses_TranscriptRecordClass: combine search
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKAnswerMeta,
    WDKSearchConfig,
    WDKStep,
    WDKStepTree,
    WDKStrategyDetails,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.wdk_conversion import (
    build_snapshot_from_wdk,
)
from veupath_chatbot.services.strategies.wdk_counts import (
    _STEP_COUNTS_CACHE,
    compute_step_counts_for_plan,
    is_leaf_only_strategy,
)
from veupath_chatbot.transport.http.routers.strategies._shared import (
    derive_steps_from_plan,
)

# WDK-verified search names (PlasmoDB transcript record type)
_SEARCH_TAXON = "GenesByTaxon"
_SEARCH_LOCATION = "GenesByLocation"
_SEARCH_BOOLEAN = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"
_RECORD_CLASS = "TranscriptRecordClasses.TranscriptRecordClass"


class TestDeriveStepsPopulatesCountsFromPlan:
    """derive_steps_from_plan should inject resultCount from plan['stepCounts']."""

    def test_counts_populated_from_step_counts_key(self) -> None:
        """Steps get resultCount from plan['stepCounts'] dict."""
        plan: JSONObject = {
            "recordType": "transcript",
            "root": {
                "id": "step_1",
                "searchName": _SEARCH_TAXON,
                "displayName": "Organism",
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            },
            "stepCounts": {
                "step_1": 150,
            },
        }
        steps = derive_steps_from_plan(plan)
        assert len(steps) == 1
        assert steps[0].result_count == 150

    def test_multi_step_counts(self) -> None:
        """Multiple steps each get their respective counts."""
        plan: JSONObject = {
            "recordType": "transcript",
            "root": {
                "id": "step_3",
                "searchName": _SEARCH_BOOLEAN,
                "displayName": "Intersect",
                "operator": "INTERSECT",
                "parameters": {},
                "primaryInput": {
                    "id": "step_1",
                    "searchName": _SEARCH_TAXON,
                    "displayName": "Organism",
                    "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                },
                "secondaryInput": {
                    "id": "step_2",
                    "searchName": _SEARCH_LOCATION,
                    "displayName": "Genomic Location",
                    "parameters": {},
                },
            },
            "stepCounts": {
                "step_1": 5000,
                "step_2": 300,
                "step_3": 42,
            },
        }
        steps = derive_steps_from_plan(plan)
        assert len(steps) == 3
        counts_by_id = {s.id: s.result_count for s in steps}
        assert counts_by_id["step_1"] == 5000
        assert counts_by_id["step_2"] == 300
        assert counts_by_id["step_3"] == 42

    def test_no_step_counts_key_backward_compatible(self) -> None:
        """When plan has no 'stepCounts', resultCount stays None (backward compat)."""
        plan: JSONObject = {
            "recordType": "transcript",
            "root": {
                "id": "step_1",
                "searchName": _SEARCH_TAXON,
                "displayName": "Organism",
                "parameters": {},
            },
        }
        steps = derive_steps_from_plan(plan)
        assert len(steps) == 1
        assert steps[0].result_count is None

    def test_partial_counts(self) -> None:
        """Only steps present in stepCounts get counts; others stay None."""
        plan: JSONObject = {
            "recordType": "transcript",
            "root": {
                "id": "step_2",
                "searchName": _SEARCH_BOOLEAN,
                "displayName": "Intersect",
                "operator": "INTERSECT",
                "parameters": {},
                "primaryInput": {
                    "id": "step_1",
                    "searchName": _SEARCH_TAXON,
                    "displayName": "Organism",
                    "parameters": {},
                },
                "secondaryInput": {
                    "id": "step_x",
                    "searchName": _SEARCH_LOCATION,
                    "displayName": "Genomic Location",
                    "parameters": {},
                },
            },
            "stepCounts": {
                "step_1": 100,
                # step_x and step_2 not in stepCounts
            },
        }
        steps = derive_steps_from_plan(plan)
        counts_by_id = {s.id: s.result_count for s in steps}
        assert counts_by_id["step_1"] == 100
        assert counts_by_id["step_x"] is None
        assert counts_by_id["step_2"] is None


class TestBuildSnapshotExtractsStepCounts:
    """_build_snapshot_from_wdk should return per-step counts from WDK steps."""

    def test_extracts_estimated_sizes(self) -> None:
        """Step counts dict is populated from steps[stepId].estimatedSize."""
        wdk_strategy = WDKStrategyDetails(
            strategy_id=500,
            name="Test Strategy",
            description="",
            root_step_id=100,
            record_class_name=_RECORD_CLASS,
            estimated_size=150,
            step_tree=WDKStepTree(step_id=100),
            steps={
                "100": WDKStep(
                    id=100,
                    search_name=_SEARCH_TAXON,
                    search_config=WDKSearchConfig(
                        parameters={
                            "organism": '["Plasmodium falciparum 3D7"]',
                        },
                    ),
                    display_name="Organism",
                    estimated_size=150,
                    record_class_name=_RECORD_CLASS,
                ),
            },
        )
        _ast, _steps_data, step_counts = build_snapshot_from_wdk(wdk_strategy)
        assert isinstance(step_counts, dict)
        assert step_counts.get("100") == 150

    def test_multi_step_extracts_all_counts(self) -> None:
        """Multi-step strategy extracts counts for all steps with estimatedSize."""
        wdk_strategy = WDKStrategyDetails(
            strategy_id=600,
            name="Multi Step",
            description="",
            root_step_id=300,
            record_class_name=_RECORD_CLASS,
            estimated_size=42,
            step_tree=WDKStepTree(
                step_id=300,
                primary_input=WDKStepTree(step_id=100),
                secondary_input=WDKStepTree(step_id=200),
            ),
            steps={
                "100": WDKStep(
                    id=100,
                    search_name=_SEARCH_TAXON,
                    search_config=WDKSearchConfig(
                        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                    ),
                    display_name="Organism",
                    estimated_size=5000,
                    record_class_name=_RECORD_CLASS,
                ),
                "200": WDKStep(
                    id=200,
                    search_name=_SEARCH_LOCATION,
                    search_config=WDKSearchConfig(parameters={}),
                    display_name="Genomic Location",
                    estimated_size=300,
                    record_class_name=_RECORD_CLASS,
                ),
                "300": WDKStep(
                    id=300,
                    search_name=_SEARCH_BOOLEAN,
                    search_config=WDKSearchConfig(
                        parameters={"bq_operator": "INTERSECT"},
                    ),
                    display_name="Intersect",
                    estimated_size=42,
                    record_class_name=_RECORD_CLASS,
                ),
            },
        )
        _ast, _steps_data, step_counts = build_snapshot_from_wdk(wdk_strategy)
        assert step_counts.get("100") == 5000
        assert step_counts.get("200") == 300
        assert step_counts.get("300") == 42

    def test_missing_estimated_size_excluded(self) -> None:
        """Steps without estimatedSize are not included in step_counts."""
        wdk_strategy = WDKStrategyDetails(
            strategy_id=700,
            name="No Count",
            description="",
            root_step_id=100,
            record_class_name=_RECORD_CLASS,
            estimated_size=None,
            step_tree=WDKStepTree(step_id=100),
            steps={
                "100": WDKStep(
                    id=100,
                    search_name=_SEARCH_TAXON,
                    search_config=WDKSearchConfig(
                        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                    ),
                    display_name="Organism",
                    record_class_name=_RECORD_CLASS,
                    # No estimated_size — defaults to None
                ),
            },
        )
        _ast, _steps_data, step_counts = build_snapshot_from_wdk(wdk_strategy)
        assert "100" not in step_counts


class TestComputeStepCountsAnonymousReports:
    """compute_step_counts_for_plan should use anonymous reports for leaf-only strategies."""

    @pytest.mark.asyncio
    async def test_leaf_only_uses_anonymous_reports(self) -> None:
        """For a plan with only search steps, anonymous reports are used (no compilation)."""
        # Clear the cache to avoid stale results
        _STEP_COUNTS_CACHE.clear()

        plan: JSONObject = {
            "recordType": "transcript",
            "root": {
                "id": "step_1",
                "searchName": _SEARCH_TAXON,
                "displayName": "Organism",
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            },
        }
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name=_SEARCH_TAXON,
                parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                display_name="Organism",
                id="step_1",
            ),
        )

        # Mock the get_strategy_api to return an API with a mock client
        mock_client = AsyncMock()
        mock_client.run_search_report = AsyncMock(
            return_value=WDKAnswer(
                meta=WDKAnswerMeta(total_count=150),
                records=[],
            )
        )

        mock_api = MagicMock()
        mock_api.client = mock_client

        # Patch get_strategy_api to return our mock
        with patch(
            "veupath_chatbot.services.strategies.wdk_counts.get_strategy_api",
            return_value=mock_api,
        ):
            counts = await compute_step_counts_for_plan(plan, ast, "plasmodb")
            assert counts["step_1"] == 150
            # Verify anonymous report was called (not compile_strategy)
            mock_client.run_search_report.assert_called_once()

        _STEP_COUNTS_CACHE.clear()

    def test_is_leaf_only_detects_combine(self) -> None:
        """is_leaf_only_strategy returns False for strategies with combine steps."""
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name=_SEARCH_BOOLEAN,
                operator=CombineOp.INTERSECT,
                display_name="Intersect",
                id="step_2",
                primary_input=PlanStepNode(
                    search_name=_SEARCH_TAXON,
                    parameters={},
                    display_name="Organism",
                    id="step_a",
                ),
                secondary_input=PlanStepNode(
                    search_name=_SEARCH_LOCATION,
                    parameters={},
                    display_name="Genomic Location",
                    id="step_b",
                ),
            ),
        )
        assert is_leaf_only_strategy(ast) is False

    def test_is_leaf_only_detects_single_search(self) -> None:
        """is_leaf_only_strategy returns True for single search step."""
        ast = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name=_SEARCH_TAXON,
                parameters={},
                display_name="Organism",
                id="step_1",
            ),
        )
        assert is_leaf_only_strategy(ast) is True
