"""Unit tests for materialization validation logic.

Tests that exercise pure validation paths (no WDK HTTP calls):
- Missing source_strategy_id raises ValidationError
- Noop when no strategy to clean up
- Error suppression during cleanup

WDK contract tests (step creation, strategy persistence, import, cleanup)
have been moved to integration/test_materialization.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.platform.errors import (
    StrategyCompilationError,
    ValidationError,
    WDKError,
)
from veupath_chatbot.services.experiment.materialization import (
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


class TestPersistImportStrategyValidation:
    async def test_raises_without_source_strategy(self) -> None:
        api = AsyncMock()
        cfg = _cfg("import")  # no source_strategy_id
        with pytest.raises(ValidationError, match="source_strategy_id is required"):
            await _persist_import_strategy(api, cfg, "exp-001")

    async def test_raises_on_bad_dup_response(self) -> None:
        api = AsyncMock()
        api.get_duplicated_step_tree.side_effect = StrategyCompilationError(
            "Failed to duplicate step tree"
        )

        cfg = _cfg("import", source_strategy_id="999")
        with pytest.raises(
            StrategyCompilationError, match="Failed to duplicate step tree"
        ):
            await _persist_import_strategy(api, cfg, "exp-001")


class TestCleanupExperimentStrategyValidation:
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

        # Should not raise -- errors are logged and suppressed
        await cleanup_experiment_strategy(exp)
