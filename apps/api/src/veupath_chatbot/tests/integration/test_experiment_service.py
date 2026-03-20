"""Integration tests for the experiment service orchestrator.

Exercises the full ``run_experiment`` lifecycle with mocked WDK
dependencies (control tests, strategy API) but real metrics computation,
store persistence, and progress-callback plumbing.

Run with:

    pytest src/veupath_chatbot/tests/integration/test_experiment_service.py -v -s
"""

import math
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.service import run_experiment
from veupath_chatbot.services.experiment.store import get_experiment_store
from veupath_chatbot.services.experiment.types import (
    ExperimentConfig,
    ExperimentMetrics,
)


def _event_data(event: JSONObject) -> JSONObject:
    """Extract the ``data`` dict from an SSE progress event.

    Narrows the ``JSONValue`` to ``JSONObject`` so subsequent attribute
    accesses satisfy mypy.
    """
    raw: JSONValue = event["data"]
    assert isinstance(raw, dict)
    return raw


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

POSITIVE_IDS = [
    "PF3D7_0100100",
    "PF3D7_0831900",
    "PF3D7_1133400",
    "PF3D7_0709000",
    "PF3D7_1343700",
    "PF3D7_0209000",
    "PF3D7_1346700",
    "PF3D7_1346800",
    "PF3D7_0935400",
    "PF3D7_0406200",
]

NEGATIVE_IDS = [
    "PF3D7_FAKE001",
    "PF3D7_FAKE002",
    "PF3D7_FAKE003",
    "PF3D7_FAKE004",
    "PF3D7_FAKE005",
]


def _make_config(**overrides: Any) -> ExperimentConfig:
    """Build a minimal single-step ExperimentConfig with sensible defaults."""
    defaults: dict[str, Any] = {
        "site_id": "PlasmoDB",
        "record_type": "gene",
        "search_name": "GenesByTaxon",
        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
        "positive_controls": list(POSITIVE_IDS),
        "negative_controls": list(NEGATIVE_IDS),
        "controls_search_name": "GenesByTextSearch",
        "controls_param_name": "text_expression",
        "name": "Test Experiment",
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def _make_control_result(
    *,
    positive_intersection_count: int = 8,
    positive_intersection_ids: list[str] | None = None,
    negative_intersection_count: int = 1,
    negative_intersection_ids: list[str] | None = None,
    target_result_count: int = 150,
    target_step_id: int = 100,
) -> JSONObject:
    """Build a realistic ``run_positive_negative_controls`` return value."""
    pos_ids = positive_intersection_ids or list(
        POSITIVE_IDS[:positive_intersection_count]
    )
    neg_ids = negative_intersection_ids or list(
        NEGATIVE_IDS[:negative_intersection_count]
    )
    pos_missing = [pid for pid in POSITIVE_IDS if pid not in set(pos_ids)]
    neg_unexpected = list(neg_ids)

    return {
        "siteId": "PlasmoDB",
        "recordType": "gene",
        "target": {
            "searchName": "GenesByTaxon",
            "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            "stepId": target_step_id,
            "resultCount": target_result_count,
        },
        "positive": {
            "controlsCount": len(POSITIVE_IDS),
            "intersectionCount": positive_intersection_count,
            "intersectionIds": list(pos_ids),
            "intersectionIdsSample": list(pos_ids[:50]),
            "targetStepId": target_step_id,
            "targetResultCount": target_result_count,
            "missingIdsSample": list(pos_missing[:50]),
            "recall": positive_intersection_count / len(POSITIVE_IDS),
        },
        "negative": {
            "controlsCount": len(NEGATIVE_IDS),
            "intersectionCount": negative_intersection_count,
            "intersectionIds": list(neg_ids),
            "intersectionIdsSample": list(neg_ids[:50]),
            "targetStepId": target_step_id,
            "targetResultCount": target_result_count,
            "unexpectedHitsSample": list(neg_unexpected[:50]),
            "falsePositiveRate": negative_intersection_count / len(NEGATIVE_IDS),
        },
    }


def _make_mock_strategy_api() -> AsyncMock:
    """Create an AsyncMock that satisfies the StrategyAPI interface."""
    api = AsyncMock()
    api.create_step.return_value = {"id": 100}
    api.create_strategy.return_value = {"id": 200}
    api.delete_strategy.return_value = None
    return api


@pytest.fixture(autouse=True)
def _reset_experiment_store() -> None:
    """Clear the cached singleton so each test gets a fresh ExperimentStore.

    ``get_experiment_store`` is decorated with ``@functools.cache``, so the
    only way to guarantee a clean store is to invalidate that cache before
    every test.
    """
    get_experiment_store.cache_clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleStepLifecycle:
    """Run a single-step experiment end-to-end and verify the result."""

    async def test_single_step_lifecycle(self) -> None:
        config = _make_config()
        control_result = _make_control_result()
        mock_callback = AsyncMock()

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config, progress_callback=mock_callback)

        assert experiment.status == "completed"
        assert experiment.metrics is not None
        assert experiment.completed_at is not None
        assert experiment.total_time_seconds is not None
        assert experiment.total_time_seconds >= 0
        assert experiment.error is None

        # Gene lists populated from control result
        assert len(experiment.true_positive_genes) == 8
        assert len(experiment.false_negative_genes) == 2
        assert len(experiment.false_positive_genes) == 1
        # True negatives: negative controls not in intersection
        assert len(experiment.true_negative_genes) == 4

        # WDK strategy was persisted
        assert experiment.wdk_strategy_id == 200
        assert experiment.wdk_step_id == 100

    async def test_experiment_id_format(self) -> None:
        """Experiment ID follows the ``exp_<hex>`` pattern."""
        config = _make_config()
        control_result = _make_control_result()

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config)

        assert experiment.id.startswith("exp_")
        assert len(experiment.id) == 16  # "exp_" + 12 hex chars


class TestProgressEvents:
    """Verify the progress callback receives expected phases."""

    async def test_progress_events_phases(self) -> None:
        config = _make_config()
        control_result = _make_control_result()
        events: list[JSONObject] = []

        async def collect(event: JSONObject) -> None:
            events.append(event)

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            await run_experiment(config, progress_callback=collect)

        # All events have the correct structure
        for event in events:
            assert event["type"] == "experiment_progress"
            data = _event_data(event)
            assert "experimentId" in data
            assert "phase" in data

        # Extract phases in order
        phases = [_event_data(event)["phase"] for event in events]

        # Must start with "started" and end with "completed"
        assert phases[0] == "started"
        assert phases[-1] == "completed"

        # Must include at least one "evaluating" phase
        assert "evaluating" in phases

    async def test_progress_events_include_experiment_id(self) -> None:
        config = _make_config()
        control_result = _make_control_result()
        events: list[JSONObject] = []

        async def collect(event: JSONObject) -> None:
            events.append(event)

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config, progress_callback=collect)

        # All events reference the correct experiment ID
        for event in events:
            data = _event_data(event)
            assert data["experimentId"] == experiment.id


class TestMetricsComputed:
    """Verify confusion matrix and derived metrics from known control results."""

    async def test_metrics_with_known_counts(self) -> None:
        """Given 8 TP, 2 FN, 1 FP, 4 TN -- verify all derived metrics."""
        config = _make_config()
        control_result = _make_control_result(
            positive_intersection_count=8,
            negative_intersection_count=1,
        )

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config)

        metrics = experiment.metrics
        assert metrics is not None
        _assert_metrics_correct(metrics)

    async def test_perfect_controls(self) -> None:
        """All positives found, zero negatives found => perfect scores."""
        config = _make_config()
        control_result = _make_control_result(
            positive_intersection_count=10,
            positive_intersection_ids=list(POSITIVE_IDS),
            negative_intersection_count=0,
            negative_intersection_ids=[],
        )

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config)

        metrics = experiment.metrics
        assert metrics is not None
        assert metrics.sensitivity == 1.0
        assert metrics.specificity == 1.0
        assert metrics.precision == 1.0
        assert metrics.f1_score == 1.0
        assert metrics.mcc == 1.0
        assert metrics.balanced_accuracy == 1.0

    async def test_no_controls_found(self) -> None:
        """Zero positives found, all negatives found => worst scores."""
        config = _make_config()
        control_result = _make_control_result(
            positive_intersection_count=0,
            positive_intersection_ids=[],
            negative_intersection_count=5,
            negative_intersection_ids=list(NEGATIVE_IDS),
        )

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config)

        metrics = experiment.metrics
        assert metrics is not None
        assert metrics.sensitivity == 0.0
        assert metrics.specificity == 0.0
        assert metrics.precision == 0.0
        assert metrics.f1_score == 0.0


def _assert_metrics_correct(metrics: ExperimentMetrics) -> None:
    """Assert metrics are consistent with TP=8, FN=2, FP=1, TN=4."""
    cm = metrics.confusion_matrix
    assert cm.true_positives == 8
    assert cm.false_negatives == 2
    assert cm.false_positives == 1
    assert cm.true_negatives == 4

    # Sensitivity = TP / (TP + FN) = 8/10 = 0.8
    assert math.isclose(metrics.sensitivity, 0.8, rel_tol=1e-9)
    # Specificity = TN / (TN + FP) = 4/5 = 0.8
    assert math.isclose(metrics.specificity, 0.8, rel_tol=1e-9)
    # Precision = TP / (TP + FP) = 8/9
    assert math.isclose(metrics.precision, 8.0 / 9.0, rel_tol=1e-9)
    # F1 harmonic mean of precision and sensitivity
    expected_precision = 8.0 / 9.0
    expected_f1 = 2 * expected_precision * 0.8 / (expected_precision + 0.8)
    assert math.isclose(metrics.f1_score, expected_f1, rel_tol=1e-9)
    # MCC
    tp, fp, tn, fn = 8, 1, 4, 2
    mcc_denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    expected_mcc = ((tp * tn) - (fp * fn)) / mcc_denom
    assert math.isclose(metrics.mcc, expected_mcc, rel_tol=1e-9)
    # Balanced accuracy = (sensitivity + specificity) / 2
    assert math.isclose(metrics.balanced_accuracy, (0.8 + 0.8) / 2.0, rel_tol=1e-9)
    # Total results from the target step
    assert metrics.total_results == 150
    assert metrics.total_positives == 10
    assert metrics.total_negatives == 5


class TestExperimentPersisted:
    """Verify experiment is saved to the store and retrievable."""

    async def test_experiment_persisted(self) -> None:
        config = _make_config()
        control_result = _make_control_result()

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=control_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config)

        store = get_experiment_store()
        stored = store.get(experiment.id)
        assert stored is not None
        assert stored.id == experiment.id
        assert stored.status == "completed"
        assert stored.config.site_id == "PlasmoDB"
        assert stored.config.name == "Test Experiment"
        assert stored.metrics is not None
        assert stored.metrics.confusion_matrix.true_positives == 8

    async def test_store_persists_during_running_state(self) -> None:
        """The store should have the experiment even before completion
        (saved once in 'running' state at the start)."""
        config = _make_config()
        store = get_experiment_store()
        captured_id: str | None = None

        async def capture_id_callback(event: JSONObject) -> None:
            nonlocal captured_id
            data = event.get("data")
            if isinstance(data, dict) and data.get("phase") == "started":
                captured_id = data.get("experimentId")
                if isinstance(captured_id, str):
                    # At this point the experiment should already be in the store
                    stored = store.get(captured_id)
                    assert stored is not None
                    assert stored.status == "running"

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=_make_control_result(),
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            await run_experiment(config, progress_callback=capture_id_callback)

        assert captured_id is not None

    async def test_list_all_returns_experiment(self) -> None:
        config = _make_config()

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=_make_control_result(),
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
        ):
            experiment = await run_experiment(config)

        store = get_experiment_store()
        all_exps = store.list_all(site_id="PlasmoDB")
        assert len(all_exps) == 1
        assert all_exps[0].id == experiment.id


class TestErrorSetsStatus:
    """Verify that failures result in error status and progress events."""

    async def test_control_test_failure_raises(self) -> None:
        """When ``run_positive_negative_controls`` raises, the experiment
        should be saved with status 'error' and the exception re-raised."""
        config = _make_config()

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                side_effect=RuntimeError("WDK connection refused"),
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
            pytest.raises(RuntimeError, match="WDK connection refused"),
        ):
            await run_experiment(config)

        # Even though it raised, the store should have the error experiment
        store = get_experiment_store()
        all_exps = store.list_all()
        assert len(all_exps) == 1
        exp = all_exps[0]
        assert exp.status == "error"
        assert exp.error == "WDK connection refused"

    async def test_error_event_emitted(self) -> None:
        """The progress callback should receive an 'error' phase event."""
        config = _make_config()
        events: list[JSONObject] = []

        async def collect(event: JSONObject) -> None:
            events.append(event)

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                side_effect=RuntimeError("WDK timeout"),
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=_make_mock_strategy_api(),
            ),
            pytest.raises(RuntimeError),
        ):
            await run_experiment(config, progress_callback=collect)

        phases = [_event_data(event)["phase"] for event in events]
        assert "started" in phases
        assert "error" in phases

        # Error event should include the error message
        error_events = [
            event for event in events if _event_data(event).get("phase") == "error"
        ]
        assert len(error_events) == 1
        error_data = _event_data(error_events[0])
        assert "WDK timeout" in str(error_data.get("error", ""))

    async def test_strategy_persist_failure_does_not_fail_experiment(self) -> None:
        """If WDK strategy creation fails, the experiment should still
        complete successfully (strategy persistence is best-effort)."""
        config = _make_config()
        failing_api = _make_mock_strategy_api()
        failing_api.create_step.side_effect = RuntimeError("WDK strategy API down")

        with (
            patch(
                "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=_make_control_result(),
            ),
            patch(
                "veupath_chatbot.services.experiment.materialization.get_strategy_api",
                return_value=failing_api,
            ),
        ):
            experiment = await run_experiment(config)

        # Experiment completes despite strategy failure
        assert experiment.status == "completed"
        assert experiment.metrics is not None
        # But WDK IDs are not set
        assert experiment.wdk_strategy_id is None
        assert experiment.wdk_step_id is None
