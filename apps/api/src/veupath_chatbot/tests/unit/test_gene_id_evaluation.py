"""Tests for gene-ID-based evaluation — pure set intersection, no WDK calls.

Covers:
- evaluate_gene_ids_against_controls: correct counts, ID lists, edge cases
- _phase_evaluate integration: gene ID mode bypasses WDK step creation
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import veupath_chatbot.services.experiment.store as store_module
from veupath_chatbot.services.experiment.metrics import (
    evaluate_gene_ids_against_controls,
    metrics_from_control_result,
)
from veupath_chatbot.services.experiment.service import _phase_evaluate
from veupath_chatbot.services.experiment.store import (
    ExperimentStore,
    get_experiment_store,
)
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    ExperimentProgressPhase,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GENE_IDS = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10"]
POSITIVE_IDS = ["G1", "G2", "G3", "G4", "G5"]
NEGATIVE_IDS = ["N1", "N2", "N3"]


def _make_config(**overrides: Any) -> ExperimentConfig:
    defaults: dict[str, Any] = {
        "site_id": "PlasmoDB",
        "record_type": "gene",
        "search_name": "",
        "parameters": {},
        "positive_controls": list(POSITIVE_IDS),
        "negative_controls": list(NEGATIVE_IDS),
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "name": "Test",
        "target_gene_ids": list(GENE_IDS),
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def _make_experiment(config: ExperimentConfig | None = None) -> Experiment:
    return Experiment(
        id="exp_test123456",
        config=config or _make_config(),
        status="running",
        created_at="2026-01-01T00:00:00",
    )


async def _noop_emit(phase: ExperimentProgressPhase, **extra: object) -> None:
    pass


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    store_module._global_store = ExperimentStore()


# ---------------------------------------------------------------------------
# evaluate_gene_ids_against_controls
# ---------------------------------------------------------------------------


class TestEvaluateGeneIdsAgainstControls:
    """Pure Python set intersection evaluation."""

    def test_all_positives_found(self) -> None:
        result = evaluate_gene_ids_against_controls(
            gene_ids=GENE_IDS,
            positive_controls=POSITIVE_IDS,
            negative_controls=[],
        )
        pos = result["positive"]
        assert isinstance(pos, dict)
        assert pos["intersectionCount"] == 5
        assert pos["controlsCount"] == 5
        assert set(pos["intersectionIds"]) == set(POSITIVE_IDS)
        assert pos["missingIdsSample"] == []

    def test_some_positives_missing(self) -> None:
        result = evaluate_gene_ids_against_controls(
            gene_ids=["G1", "G3"],
            positive_controls=POSITIVE_IDS,
            negative_controls=[],
        )
        pos = result["positive"]
        assert isinstance(pos, dict)
        assert pos["intersectionCount"] == 2
        assert pos["controlsCount"] == 5
        assert set(pos["intersectionIds"]) == {"G1", "G3"}
        assert set(pos["missingIdsSample"]) == {"G2", "G4", "G5"}

    def test_negatives_excluded(self) -> None:
        result = evaluate_gene_ids_against_controls(
            gene_ids=GENE_IDS,
            positive_controls=[],
            negative_controls=NEGATIVE_IDS,
        )
        neg = result["negative"]
        assert isinstance(neg, dict)
        assert neg["intersectionCount"] == 0
        assert neg["controlsCount"] == 3
        assert neg["intersectionIds"] == []

    def test_some_negatives_leak_through(self) -> None:
        gene_ids = [*GENE_IDS, "N1"]  # N1 leaked into results
        result = evaluate_gene_ids_against_controls(
            gene_ids=gene_ids,
            positive_controls=[],
            negative_controls=NEGATIVE_IDS,
        )
        neg = result["negative"]
        assert isinstance(neg, dict)
        assert neg["intersectionCount"] == 1
        assert neg["intersectionIds"] == ["N1"]

    def test_target_result_count_matches_gene_ids(self) -> None:
        result = evaluate_gene_ids_against_controls(
            gene_ids=GENE_IDS,
            positive_controls=POSITIVE_IDS,
            negative_controls=NEGATIVE_IDS,
        )
        target = result["target"]
        assert isinstance(target, dict)
        assert target["resultCount"] == len(GENE_IDS)

    def test_empty_controls(self) -> None:
        result = evaluate_gene_ids_against_controls(
            gene_ids=GENE_IDS,
            positive_controls=[],
            negative_controls=[],
        )
        assert result["positive"] is None
        assert result["negative"] is None

    def test_whitespace_controls_stripped(self) -> None:
        result = evaluate_gene_ids_against_controls(
            gene_ids=["G1", "G2"],
            positive_controls=["  G1  ", " ", "G3"],
            negative_controls=[],
        )
        pos = result["positive"]
        assert isinstance(pos, dict)
        assert pos["intersectionCount"] == 1
        assert pos["controlsCount"] == 2  # whitespace-only stripped

    def test_compatible_with_metrics_from_control_result(self) -> None:
        """The returned dict must be consumable by metrics_from_control_result."""
        result = evaluate_gene_ids_against_controls(
            gene_ids=GENE_IDS,
            positive_controls=POSITIVE_IDS,
            negative_controls=NEGATIVE_IDS,
        )
        metrics = metrics_from_control_result(result)
        assert metrics.sensitivity == 1.0  # all 5 positives found
        assert metrics.specificity == 1.0  # no negatives found
        assert metrics.total_results == 10


# ---------------------------------------------------------------------------
# _phase_evaluate with gene IDs
# ---------------------------------------------------------------------------


class TestPhaseEvaluateWithGeneIds:
    """_phase_evaluate uses gene IDs directly, skipping WDK step creation."""

    async def test_gene_id_mode_skips_wdk_calls(self) -> None:
        """When target_gene_ids is set, no WDK control tests should run."""
        config = _make_config(target_gene_ids=list(GENE_IDS))
        experiment = _make_experiment(config)
        store = get_experiment_store()

        # Patch the WDK-based functions to verify they're NOT called
        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
            ) as mock_wdk,
            patch(
                "veupath_chatbot.services.experiment.service.run_controls_against_tree",
                new_callable=AsyncMock,
            ) as mock_tree,
        ):
            _result, metrics = await _phase_evaluate(
                config, experiment, _noop_emit, store
            )

        mock_wdk.assert_not_awaited()
        mock_tree.assert_not_awaited()
        assert metrics is not None
        assert experiment.metrics is metrics
        assert metrics.sensitivity == 1.0

    async def test_gene_id_mode_populates_gene_lists(self) -> None:
        config = _make_config(target_gene_ids=list(GENE_IDS))
        experiment = _make_experiment(config)
        store = get_experiment_store()

        await _phase_evaluate(config, experiment, _noop_emit, store)

        assert len(experiment.true_positive_genes) == 5
        assert len(experiment.false_negative_genes) == 0
        assert len(experiment.false_positive_genes) == 0
        assert len(experiment.true_negative_genes) == 3
