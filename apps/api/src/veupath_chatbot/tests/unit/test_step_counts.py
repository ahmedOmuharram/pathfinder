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

from unittest.mock import AsyncMock, MagicMock

import pytest

import veupath_chatbot.services.strategies.wdk_counts as bridge_module
from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.ops import CombineOp
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
        wdk_strategy: JSONObject = {
            "strategyId": 500,
            "name": "Test Strategy",
            "description": "",
            "isSaved": False,
            "isPublic": False,
            "isDeleted": False,
            "isValid": True,
            "rootStepId": 100,
            "estimatedSize": 150,
            "recordClassName": _RECORD_CLASS,
            "signature": "abc123",
            "stepTree": {"stepId": 100},
            "steps": {
                "100": {
                    "id": 100,
                    "searchName": _SEARCH_TAXON,
                    "searchConfig": {
                        "parameters": {
                            "organism": '["Plasmodium falciparum 3D7"]',
                        },
                        "wdkWeight": 0,
                    },
                    "displayName": "Organism",
                    "customName": None,
                    "estimatedSize": 150,
                    "recordClassName": _RECORD_CLASS,
                    "isFiltered": False,
                    "hasCompleteStepAnalyses": False,
                }
            },
        }
        _ast, _steps_data, step_counts = build_snapshot_from_wdk(wdk_strategy)
        assert isinstance(step_counts, dict)
        assert step_counts.get("100") == 150

    def test_multi_step_extracts_all_counts(self) -> None:
        """Multi-step strategy extracts counts for all steps with estimatedSize."""
        wdk_strategy: JSONObject = {
            "strategyId": 600,
            "name": "Multi Step",
            "description": "",
            "isSaved": False,
            "isPublic": False,
            "isDeleted": False,
            "isValid": True,
            "rootStepId": 300,
            "estimatedSize": 42,
            "recordClassName": _RECORD_CLASS,
            "signature": "def456",
            "stepTree": {
                "stepId": 300,
                "primaryInput": {"stepId": 100},
                "secondaryInput": {"stepId": 200},
            },
            "steps": {
                "100": {
                    "id": 100,
                    "searchName": _SEARCH_TAXON,
                    "searchConfig": {
                        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                    },
                    "displayName": "Organism",
                    "customName": None,
                    "estimatedSize": 5000,
                    "recordClassName": _RECORD_CLASS,
                },
                "200": {
                    "id": 200,
                    "searchName": _SEARCH_LOCATION,
                    "searchConfig": {
                        "parameters": {},
                    },
                    "displayName": "Genomic Location",
                    "customName": None,
                    "estimatedSize": 300,
                    "recordClassName": _RECORD_CLASS,
                },
                "300": {
                    "id": 300,
                    "searchName": _SEARCH_BOOLEAN,
                    "searchConfig": {
                        "parameters": {
                            "bq_operator": "INTERSECT",
                        },
                    },
                    "displayName": "Intersect",
                    "customName": None,
                    "estimatedSize": 42,
                    "recordClassName": _RECORD_CLASS,
                },
            },
        }
        _ast, _steps_data, step_counts = build_snapshot_from_wdk(wdk_strategy)
        assert step_counts.get("100") == 5000
        assert step_counts.get("200") == 300
        assert step_counts.get("300") == 42

    def test_missing_estimated_size_excluded(self) -> None:
        """Steps without estimatedSize are not included in step_counts."""
        wdk_strategy: JSONObject = {
            "strategyId": 700,
            "name": "No Count",
            "description": "",
            "isSaved": False,
            "isPublic": False,
            "isDeleted": False,
            "isValid": True,
            "rootStepId": 100,
            "estimatedSize": None,
            "recordClassName": _RECORD_CLASS,
            "signature": "ghi789",
            "stepTree": {"stepId": 100},
            "steps": {
                "100": {
                    "id": 100,
                    "searchName": _SEARCH_TAXON,
                    "searchConfig": {
                        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
                    },
                    "displayName": "Organism",
                    "customName": None,
                    "recordClassName": _RECORD_CLASS,
                    # No estimatedSize key
                }
            },
        }
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
            return_value={
                "meta": {"totalCount": 150, "displayRange": {"start": 0, "end": 0}},
                "records": [],
            }
        )

        mock_api = MagicMock()
        mock_api.client = mock_client

        # Patch get_strategy_api to return our mock
        original_get_api = bridge_module.get_strategy_api
        bridge_module.get_strategy_api = lambda _: mock_api

        try:
            counts = await compute_step_counts_for_plan(plan, ast, "plasmodb")
            assert counts["step_1"] == 150
            # Verify anonymous report was called (not compile_strategy)
            mock_client.run_search_report.assert_called_once()
        finally:
            bridge_module.get_strategy_api = original_get_api
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
