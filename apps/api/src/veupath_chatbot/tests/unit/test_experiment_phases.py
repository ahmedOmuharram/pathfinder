"""Unit tests for experiment service phase functions.

Tests each phase function independently with mocked dependencies.
The existing integration tests in test_experiment_service.py cover
the full run_experiment() orchestration.
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import veupath_chatbot.services.experiment.store as store_module
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.service import (
    _phase_cross_validate,
    _phase_enrich,
    _phase_evaluate,
    _phase_persist_strategy,
    _phase_rank_metrics,
    _phase_robustness,
)
from veupath_chatbot.services.experiment.store import (
    ExperimentStore,
    get_experiment_store,
)
from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentProgressPhase,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

POSITIVE_IDS = ["G1", "G2", "G3", "G4", "G5"]
NEGATIVE_IDS = ["N1", "N2", "N3"]


def _make_config(**overrides: Any) -> ExperimentConfig:
    defaults: dict[str, Any] = {
        "site_id": "PlasmoDB",
        "record_type": "gene",
        "search_name": "GenesByTaxon",
        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
        "positive_controls": list(POSITIVE_IDS),
        "negative_controls": list(NEGATIVE_IDS),
        "controls_search_name": "GenesByTextSearch",
        "controls_param_name": "text_expression",
        "name": "Test",
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


def _make_control_result(
    pos_count: int = 4,
    neg_count: int = 1,
    step_id: int = 100,
    result_count: int = 150,
) -> JSONObject:
    pos_ids = list(POSITIVE_IDS[:pos_count])
    neg_ids = list(NEGATIVE_IDS[:neg_count])
    return {
        "siteId": "PlasmoDB",
        "recordType": "gene",
        "target": {
            "searchName": "GenesByTaxon",
            "parameters": {},
            "stepId": step_id,
            "resultCount": result_count,
        },
        "positive": {
            "controlsCount": len(POSITIVE_IDS),
            "intersectionCount": pos_count,
            "intersectionIds": pos_ids,
            "intersectionIdsSample": pos_ids,
            "targetStepId": step_id,
            "targetResultCount": result_count,
            "missingIdsSample": [g for g in POSITIVE_IDS if g not in pos_ids],
            "recall": pos_count / len(POSITIVE_IDS),
        },
        "negative": {
            "controlsCount": len(NEGATIVE_IDS),
            "intersectionCount": neg_count,
            "intersectionIds": neg_ids,
            "intersectionIdsSample": neg_ids,
            "targetStepId": step_id,
            "targetResultCount": result_count,
            "unexpectedHitsSample": neg_ids,
            "falsePositiveRate": neg_count / len(NEGATIVE_IDS),
        },
    }


async def _noop_emit(phase: ExperimentProgressPhase, **extra: object) -> None:
    pass


def _tracking_emit() -> tuple[
    list[tuple[ExperimentProgressPhase, dict[str, object]]],
    Any,
]:
    """Returns (events_list, emit_fn) where emit_fn records calls."""
    events: list[tuple[ExperimentProgressPhase, dict[str, object]]] = []

    async def emit(phase: ExperimentProgressPhase, **extra: object) -> None:
        events.append((phase, extra))

    return events, emit


def _make_metrics() -> ExperimentMetrics:
    return ExperimentMetrics(
        confusion_matrix=ConfusionMatrix(
            true_positives=4,
            false_positives=1,
            true_negatives=2,
            false_negatives=1,
        ),
        sensitivity=0.8,
        specificity=0.67,
        precision=0.8,
        f1_score=0.8,
        mcc=0.47,
        balanced_accuracy=0.73,
        total_results=100,
        total_positives=5,
        total_negatives=3,
    )


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    store_module._global_store = ExperimentStore()


# ---------------------------------------------------------------------------
# Phase -evaluate
# ---------------------------------------------------------------------------


class TestPhaseEvaluate:
    """_phase_evaluate runs control tests, computes metrics, enriches genes."""

    async def test_single_step_returns_result_and_metrics(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        store = get_experiment_store()
        control_result = _make_control_result()

        with patch(
            "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
            new_callable=AsyncMock,
            return_value=control_result,
        ):
            result, metrics = await _phase_evaluate(
                config, experiment, _noop_emit, store
            )

        assert result is control_result
        assert metrics is not None
        assert experiment.metrics is metrics
        assert len(experiment.true_positive_genes) == 4
        assert len(experiment.false_negative_genes) == 1

    async def test_tree_mode_uses_run_controls_against_tree(self) -> None:
        tree = {"searchName": "GenesByTaxon", "parameters": {}}
        config = _make_config(mode="multi-step", step_tree=tree)
        experiment = _make_experiment(config)
        store = get_experiment_store()
        control_result = _make_control_result()

        with patch(
            "veupath_chatbot.services.experiment.service.run_controls_against_tree",
            new_callable=AsyncMock,
            return_value=control_result,
        ) as mock_tree:
            result, _metrics = await _phase_evaluate(
                config, experiment, _noop_emit, store
            )

        mock_tree.assert_awaited_once()
        assert result is control_result
        assert experiment.metrics is not None

    async def test_emits_evaluating_progress(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        store = get_experiment_store()
        events, emit = _tracking_emit()

        with patch(
            "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
            new_callable=AsyncMock,
            return_value=_make_control_result(),
        ):
            await _phase_evaluate(config, experiment, emit, store)

        phases = [e[0] for e in events]
        assert "evaluating" in phases

    async def test_saves_to_store(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        store = get_experiment_store()
        store.save(experiment)

        with patch(
            "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
            new_callable=AsyncMock,
            return_value=_make_control_result(),
        ):
            await _phase_evaluate(config, experiment, _noop_emit, store)

        stored = store.get(experiment.id)
        assert stored is not None
        assert stored.metrics is not None


# ---------------------------------------------------------------------------
# Phase -persist_strategy
# ---------------------------------------------------------------------------


class TestPhasePersistStrategy:
    """_phase_persist_strategy creates a WDK strategy (best-effort)."""

    async def test_sets_wdk_ids_on_success(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        store = get_experiment_store()
        store.save(experiment)

        with patch(
            "veupath_chatbot.services.experiment.service._persist_experiment_strategy",
            new_callable=AsyncMock,
            return_value={"strategy_id": 200, "step_id": 100},
        ):
            await _phase_persist_strategy(config, experiment, store, None)

        assert experiment.wdk_strategy_id == 200
        assert experiment.wdk_step_id == 100

    async def test_tolerates_failure(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        store = get_experiment_store()
        store.save(experiment)

        with patch(
            "veupath_chatbot.services.experiment.service._persist_experiment_strategy",
            new_callable=AsyncMock,
            side_effect=WDKError(detail="WDK down"),
        ):
            await _phase_persist_strategy(config, experiment, store, None)

        assert experiment.wdk_strategy_id is None
        assert experiment.wdk_step_id is None


# ---------------------------------------------------------------------------
# Phase -rank_metrics
# ---------------------------------------------------------------------------


class TestPhaseRankMetrics:
    """_phase_rank_metrics computes rank-based metrics when configured."""

    async def test_computes_rank_metrics_and_returns_ordered_ids(self) -> None:
        config = _make_config(sort_attribute="fold_change")
        experiment = _make_experiment(config)
        experiment.wdk_step_id = 100
        store = get_experiment_store()
        store.save(experiment)

        fake_ids = ["G1", "G3", "G5", "N1", "G2"]

        with (
            patch(
                "veupath_chatbot.services.experiment.service.fetch_ordered_result_ids",
                new_callable=AsyncMock,
                return_value=fake_ids,
            ),
            patch(
                "veupath_chatbot.services.experiment.service.compute_rank_metrics",
                return_value=object(),  # sentinel
            ) as mock_compute,
        ):
            ordered = await _phase_rank_metrics(config, experiment, _noop_emit, store)

        assert ordered is fake_ids
        mock_compute.assert_called_once()
        assert experiment.rank_metrics is not None

    async def test_skips_when_no_sort_attribute(self) -> None:
        config = _make_config(sort_attribute=None)
        experiment = _make_experiment(config)
        experiment.wdk_step_id = 100
        store = get_experiment_store()

        ordered = await _phase_rank_metrics(config, experiment, _noop_emit, store)

        assert ordered == []
        assert experiment.rank_metrics is None

    async def test_skips_when_no_step_id(self) -> None:
        config = _make_config(sort_attribute="fold_change")
        experiment = _make_experiment(config)
        experiment.wdk_step_id = None
        store = get_experiment_store()

        ordered = await _phase_rank_metrics(config, experiment, _noop_emit, store)

        assert ordered == []

    async def test_tolerates_failure(self) -> None:
        config = _make_config(sort_attribute="fold_change")
        experiment = _make_experiment(config)
        experiment.wdk_step_id = 100
        store = get_experiment_store()

        with patch(
            "veupath_chatbot.services.experiment.service.fetch_ordered_result_ids",
            new_callable=AsyncMock,
            side_effect=ValueError("fetch failed"),
        ):
            ordered = await _phase_rank_metrics(config, experiment, _noop_emit, store)

        assert ordered == []
        assert experiment.rank_metrics is None


# ---------------------------------------------------------------------------
# Phase -robustness
# ---------------------------------------------------------------------------


class TestPhaseRobustness:
    """_phase_robustness computes bootstrap confidence intervals."""

    async def test_uses_provided_ordered_ids(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        experiment.wdk_step_id = 100
        store = get_experiment_store()
        ids = ["G1", "G2", "G3"]

        with patch(
            "veupath_chatbot.services.experiment.service.compute_robustness",
            return_value=object(),
        ) as mock_robust:
            await _phase_robustness(
                config, experiment, _noop_emit, store, ids, is_ranked=False
            )

        mock_robust.assert_called_once()
        assert experiment.robustness is not None

    async def test_fetches_ids_when_not_provided(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        experiment.wdk_step_id = 100
        store = get_experiment_store()

        with (
            patch(
                "veupath_chatbot.services.experiment.service.fetch_ordered_result_ids",
                new_callable=AsyncMock,
                return_value=["G1", "G2"],
            ),
            patch(
                "veupath_chatbot.services.experiment.service.compute_robustness",
                return_value=object(),
            ),
        ):
            await _phase_robustness(
                config, experiment, _noop_emit, store, [], is_ranked=False
            )

        assert experiment.robustness is not None

    async def test_skips_when_no_step_id(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        experiment.wdk_step_id = None
        store = get_experiment_store()

        await _phase_robustness(
            config, experiment, _noop_emit, store, [], is_ranked=False
        )

        assert experiment.robustness is None

    async def test_tolerates_failure(self) -> None:
        config = _make_config()
        experiment = _make_experiment(config)
        experiment.wdk_step_id = 100
        store = get_experiment_store()

        with patch(
            "veupath_chatbot.services.experiment.service.compute_robustness",
            side_effect=ValueError("boom"),
        ):
            await _phase_robustness(
                config, experiment, _noop_emit, store, ["G1"], is_ranked=False
            )

        assert experiment.robustness is None


# ---------------------------------------------------------------------------
# Phase -cross_validate
# ---------------------------------------------------------------------------


class TestPhaseCrossValidate:
    """_phase_cross_validate runs k-fold cross-validation."""

    async def test_single_step_cross_validation(self) -> None:
        config = _make_config(enable_cross_validation=True, k_folds=3)
        experiment = _make_experiment(config)
        store = get_experiment_store()
        store.save(experiment)
        metrics = _make_metrics()
        sentinel = object()

        with patch(
            "veupath_chatbot.services.experiment.service.run_cross_validation",
            new_callable=AsyncMock,
            return_value=sentinel,
        ) as mock_cv:
            await _phase_cross_validate(
                config,
                experiment,
                _noop_emit,
                store,
                metrics=metrics,
                final_tree=None,
                cvf="newline",
            )

        mock_cv.assert_awaited_once()
        assert experiment.cross_validation is sentinel

    async def test_tree_mode_uses_tree_cross_validation(self) -> None:
        tree: JSONObject = {"searchName": "X", "parameters": {}}
        config = _make_config(
            mode="multi-step",
            step_tree=tree,
            enable_cross_validation=True,
        )
        experiment = _make_experiment(config)
        store = get_experiment_store()
        store.save(experiment)
        metrics = _make_metrics()
        sentinel = object()

        with patch(
            "veupath_chatbot.services.experiment.service.run_cross_validation",
            new_callable=AsyncMock,
            return_value=sentinel,
        ) as mock_cv:
            await _phase_cross_validate(
                config,
                experiment,
                _noop_emit,
                store,
                metrics=metrics,
                final_tree=tree,
                cvf="newline",
            )

        mock_cv.assert_awaited_once()
        # Verify tree was passed through
        call_kwargs = mock_cv.call_args.kwargs
        assert call_kwargs["tree"] is tree
        assert experiment.cross_validation is sentinel


# ---------------------------------------------------------------------------
# Phase -enrich
# ---------------------------------------------------------------------------


class TestPhaseEnrich:
    """_phase_enrich runs enrichment analyses."""

    async def test_runs_enrichment_and_stores_results(self) -> None:
        config = _make_config(enrichment_types=["go_function"])
        experiment = _make_experiment(config)
        store = get_experiment_store()
        store.save(experiment)

        mock_svc = AsyncMock()
        mock_svc.run_batch.return_value = (
            [{"analysisType": "go_function", "terms": []}],
            [],
        )

        with patch(
            "veupath_chatbot.services.experiment.service.EnrichmentService",
            return_value=mock_svc,
        ):
            await _phase_enrich(config, experiment, _noop_emit, store)

        mock_svc.run_batch.assert_awaited_once()
        assert len(experiment.enrichment_results) > 0

    async def test_emits_enriching_progress(self) -> None:
        config = _make_config(enrichment_types=["go_function"])
        experiment = _make_experiment(config)
        store = get_experiment_store()
        events, emit = _tracking_emit()

        mock_svc = AsyncMock()
        mock_svc.run_batch.return_value = ([], [])

        with patch(
            "veupath_chatbot.services.experiment.service.EnrichmentService",
            return_value=mock_svc,
        ):
            await _phase_enrich(config, experiment, emit, store)

        phases = [e[0] for e in events]
        assert "enriching" in phases
