"""Tests for the threshold sweep service (services/experiment/sweep_service.py).

Extracted from evaluation.py to separate re-evaluation (single re-run)
from threshold sweep (batch orchestration with concurrency, timeouts, SSE).
"""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.services.experiment.sweep_service import (
    cleanup_before_sweep,
    compute_sweep_values,
    format_metrics_dict,
    generate_sweep_events,
    run_sweep_point,
    validate_sweep_parameter,
)
from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
)
from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides: object) -> ExperimentConfig:
    defaults = {
        "site_id": "PlasmoDB",
        "record_type": "transcript",
        "search_name": "GenesByTaxon",
        "parameters": {"organism": "Plasmodium falciparum 3D7", "threshold": "0.5"},
        "positive_controls": ["PF3D7_0100100", "PF3D7_0100200"],
        "negative_controls": ["PF3D7_9999999"],
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "controls_value_format": "newline",
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def _make_experiment(**overrides: object) -> Experiment:
    config_overrides = overrides.pop("config_overrides", {})
    defaults: dict[str, object] = {
        "id": "exp-001",
        "config": _make_config(**config_overrides),
        "user_id": "user-1",
        "status": "completed",
    }
    defaults.update(overrides)
    return Experiment(**defaults)


def _make_metrics() -> ExperimentMetrics:
    return ExperimentMetrics(
        confusion_matrix=ConfusionMatrix(
            true_positives=8,
            false_positives=1,
            true_negatives=9,
            false_negatives=2,
        ),
        sensitivity=0.8,
        specificity=0.9,
        precision=0.75,
        f1_score=0.77,
        mcc=0.7,
        balanced_accuracy=0.85,
        false_positive_rate=0.1,
        total_results=100,
    )


# ---------------------------------------------------------------------------
# compute_sweep_values
# ---------------------------------------------------------------------------


class TestComputeSweepValues:
    def test_numeric_basic(self) -> None:
        vals = compute_sweep_values(
            sweep_type="numeric",
            values=None,
            min_value=0.0,
            max_value=1.0,
            steps=3,
        )
        assert len(vals) == 3
        assert float(vals[0]) == pytest.approx(0.0)
        assert float(vals[1]) == pytest.approx(0.5)
        assert float(vals[2]) == pytest.approx(1.0)

    def test_categorical_basic(self) -> None:
        vals = compute_sweep_values(
            sweep_type="categorical",
            values=["a", "b", "c"],
            min_value=None,
            max_value=None,
            steps=10,
        )
        assert vals == ["a", "b", "c"]

    def test_categorical_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            compute_sweep_values(
                sweep_type="categorical",
                values=[],
                min_value=None,
                max_value=None,
                steps=10,
            )


# ---------------------------------------------------------------------------
# validate_sweep_parameter
# ---------------------------------------------------------------------------


class TestValidateSweepParameter:
    def test_valid_param(self) -> None:
        exp = _make_experiment()
        validate_sweep_parameter(exp, "threshold")

    def test_missing_param_raises(self) -> None:
        exp = _make_experiment()
        with pytest.raises(ValidationError):
            validate_sweep_parameter(exp, "not_a_param")


# ---------------------------------------------------------------------------
# format_metrics_dict
# ---------------------------------------------------------------------------


class TestFormatMetricsDict:
    def test_keys_present(self) -> None:
        m = _make_metrics()
        result = format_metrics_dict(m)
        expected_keys = {
            "sensitivity",
            "specificity",
            "precision",
            "f1Score",
            "mcc",
            "balancedAccuracy",
            "totalResults",
            "falsePositiveRate",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# run_sweep_point
# ---------------------------------------------------------------------------


class TestRunSweepPoint:
    @pytest.mark.asyncio
    async def test_successful_numeric_point(self) -> None:
        exp = _make_experiment()
        mock_result = ControlTestResult(
            positive=ControlSetData(intersection_count=2, controls_count=2),
            negative=ControlSetData(intersection_count=0, controls_count=1),
            target=ControlTargetData(estimated_size=50),
        )
        with patch(
            "veupath_chatbot.services.experiment.sweep_service.run_positive_negative_controls",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            point = await run_sweep_point(
                exp=exp,
                param_name="threshold",
                value="0.75",
                is_categorical=False,
            )

        assert point["value"] == pytest.approx(0.75)
        assert point["metrics"] is not None

    @pytest.mark.asyncio
    async def test_failure_returns_error(self) -> None:
        exp = _make_experiment()
        with patch(
            "veupath_chatbot.services.experiment.sweep_service.run_positive_negative_controls",
            new_callable=AsyncMock,
            side_effect=RuntimeError("WDK down"),
        ):
            point = await run_sweep_point(
                exp=exp,
                param_name="threshold",
                value="0.5",
                is_categorical=False,
            )

        assert point["metrics"] is None
        assert "WDK down" in point["error"]


# ---------------------------------------------------------------------------
# generate_sweep_events
# ---------------------------------------------------------------------------


class TestGenerateSweepEvents:
    @pytest.mark.asyncio
    async def test_emits_point_and_complete_events(self) -> None:
        exp = _make_experiment()
        mock_result = ControlTestResult(
            positive=ControlSetData(intersection_count=2, controls_count=2),
            negative=ControlSetData(intersection_count=0, controls_count=1),
            target=ControlTargetData(estimated_size=50),
        )

        with (
            patch(
                "veupath_chatbot.services.experiment.sweep_service.cleanup_before_sweep",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.experiment.sweep_service.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            events = [
                event
                async for event in generate_sweep_events(
                    exp=exp,
                    param_name="threshold",
                    sweep_type="numeric",
                    sweep_values=["0.0", "0.5", "1.0"],
                )
            ]

        point_events = [e for e in events if "sweep_point" in e]
        complete_events = [e for e in events if "sweep_complete" in e]
        assert len(point_events) == 3
        assert len(complete_events) == 1


# ---------------------------------------------------------------------------
# cleanup_before_sweep
# ---------------------------------------------------------------------------


class TestCleanupBeforeSweep:
    @pytest.mark.asyncio
    async def test_suppresses_errors(self) -> None:
        """cleanup_before_sweep should not raise even if internals fail."""
        with patch(
            "veupath_chatbot.services.experiment.sweep_service.get_strategy_api",
            side_effect=RuntimeError("no api"),
        ):
            # Should NOT raise
            await cleanup_before_sweep("plasmodb")
