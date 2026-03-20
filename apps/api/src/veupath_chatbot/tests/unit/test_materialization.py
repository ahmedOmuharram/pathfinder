"""Tests for WDK strategy materialization.

These tests mock the StrategyAPI to test the materialization logic without
making actual WDK calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.platform.errors import (
    StrategyCompilationError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.services.experiment.materialization import (
    _materialize_step_tree,
    _persist_experiment_strategy,
    _persist_import_strategy,
    cleanup_experiment_strategy,
)
from veupath_chatbot.services.experiment.types import Experiment, ExperimentConfig


def _cfg(
    mode: str = "single",
    source_strategy_id: str | None = None,
) -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmo",
        record_type="gene",
        search_name="GenesByText",
        parameters={"text": "kinase"},
        positive_controls=["g1"],
        negative_controls=["n1"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
        name="Test",
        mode=mode,
        source_strategy_id=source_strategy_id,
    )


class TestMaterializeStepTree:
    async def test_leaf_node(self) -> None:
        api = AsyncMock()
        api.create_step.return_value = {"id": 100}

        node = {
            "searchName": "GenesByText",
            "parameters": {"text": "kinase"},
            "displayName": "Text Search",
        }
        result = await _materialize_step_tree(api, node, "gene")

        assert result.step_id == 100
        assert result.primary_input is None
        assert result.secondary_input is None
        api.create_step.assert_called_once()

    async def test_transform_node(self) -> None:
        api = AsyncMock()
        # First call: leaf step creation
        api.create_step.return_value = {"id": 100}
        # Second call: transform step creation
        api.create_transform_step.return_value = {"id": 200}

        node = {
            "searchName": "GenesByTFBS",
            "parameters": {"tfbs": "AP2"},
            "primaryInput": {
                "searchName": "GenesByText",
                "parameters": {"text": "kinase"},
            },
        }
        result = await _materialize_step_tree(api, node, "gene")

        assert result.step_id == 200
        assert result.primary_input is not None
        assert result.primary_input.step_id == 100
        assert result.secondary_input is None

    async def test_combine_node(self) -> None:
        api = AsyncMock()
        api.create_step.side_effect = [{"id": 100}, {"id": 200}]
        api.create_combined_step.return_value = {"id": 300}

        node = {
            "searchName": "combined",
            "operator": "INTERSECT",
            "primaryInput": {
                "searchName": "GenesByText",
                "parameters": {"text": "kinase"},
            },
            "secondaryInput": {
                "searchName": "GenesByText",
                "parameters": {"text": "phosphatase"},
            },
        }
        result = await _materialize_step_tree(api, node, "gene")

        assert result.step_id == 300
        assert result.primary_input is not None
        assert result.secondary_input is not None
        api.create_combined_step.assert_called_once()


class TestPersistExperimentStrategy:
    @patch("veupath_chatbot.services.experiment.materialization.get_strategy_api")
    async def test_single_mode(self, mock_get_api: MagicMock) -> None:
        api = AsyncMock()
        api.create_step.return_value = {"id": 100}
        api.create_strategy.return_value = {"id": 500}
        mock_get_api.return_value = api

        result = await _persist_experiment_strategy(_cfg("single"), "exp-001")

        assert result["strategy_id"] == 500
        assert result["step_id"] == 100
        api.create_step.assert_called_once()
        api.create_strategy.assert_called_once()

    @patch("veupath_chatbot.services.experiment.materialization.get_strategy_api")
    async def test_multi_step_mode(self, mock_get_api: MagicMock) -> None:
        api = AsyncMock()
        api.create_step.return_value = {"id": 100}
        api.create_strategy.return_value = {"id": 500}
        mock_get_api.return_value = api

        cfg = _cfg("multi-step")
        cfg.step_tree = {
            "searchName": "GenesByText",
            "parameters": {"text": "kinase"},
        }
        result = await _persist_experiment_strategy(cfg, "exp-001")

        assert result["strategy_id"] == 500
        assert result["step_id"] == 100

    @patch("veupath_chatbot.services.experiment.materialization.get_strategy_api")
    async def test_raises_on_failed_strategy_creation(
        self, mock_get_api: MagicMock
    ) -> None:
        api = AsyncMock()
        api.create_step.return_value = {"id": 100}
        api.create_strategy.return_value = {}  # no "id" key
        mock_get_api.return_value = api

        with pytest.raises(StrategyCompilationError, match="Failed to create WDK strategy"):
            await _persist_experiment_strategy(_cfg("single"), "exp-001")


class TestPersistImportStrategy:
    async def test_successful_import(self) -> None:
        api = AsyncMock()
        api.user_id = "test-user"
        api.client = AsyncMock()
        api.client.post.return_value = {
            "stepTree": {
                "stepId": 100,
                "primaryInput": {
                    "stepId": 50,
                },
            }
        }
        api.create_strategy.return_value = {"id": 500}

        cfg = _cfg("import", source_strategy_id="999")
        result = await _persist_import_strategy(api, cfg, "exp-001")

        assert result["strategy_id"] == 500
        assert result["step_id"] == 100

    async def test_raises_without_source_strategy(self) -> None:
        api = AsyncMock()
        cfg = _cfg("import")  # no source_strategy_id
        with pytest.raises(ValidationError, match="source_strategy_id is required"):
            await _persist_import_strategy(api, cfg, "exp-001")

    async def test_raises_on_bad_dup_response(self) -> None:
        api = AsyncMock()
        api.user_id = "test-user"
        api.client = AsyncMock()
        api.client.post.return_value = {"error": "not found"}

        cfg = _cfg("import", source_strategy_id="999")
        with pytest.raises(StrategyCompilationError, match="Failed to duplicate step tree"):
            await _persist_import_strategy(api, cfg, "exp-001")


class TestCleanupExperimentStrategy:
    @patch("veupath_chatbot.services.experiment.materialization.get_strategy_api")
    async def test_deletes_strategy(self, mock_get_api: MagicMock) -> None:
        api = AsyncMock()
        mock_get_api.return_value = api

        exp = Experiment(id="exp-001", config=_cfg())
        exp.wdk_strategy_id = 42

        await cleanup_experiment_strategy(exp)
        api.delete_strategy.assert_called_once_with(42)

    async def test_noop_when_no_strategy(self) -> None:
        exp = Experiment(id="exp-001", config=_cfg())
        exp.wdk_strategy_id = None

        # Should not raise
        await cleanup_experiment_strategy(exp)

    @patch("veupath_chatbot.services.experiment.materialization.get_strategy_api")
    async def test_suppresses_delete_errors(self, mock_get_api: MagicMock) -> None:
        api = AsyncMock()
        api.delete_strategy.side_effect = WDKError(detail="WDK down")
        mock_get_api.return_value = api

        exp = Experiment(id="exp-001", config=_cfg())
        exp.wdk_strategy_id = 42

        # Should not raise — errors are logged and suppressed
        await cleanup_experiment_strategy(exp)
