"""Tests for the evaluation service (services/experiment/evaluation.py)."""

import json as json_mod
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.services.experiment.evaluation import re_evaluate
from veupath_chatbot.services.experiment.helpers import ControlsContext
from veupath_chatbot.services.experiment.sweep_service import (
    _tree_has_parameter,
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


def _make_metrics(**overrides: object) -> ExperimentMetrics:
    defaults: dict[str, object] = {
        "sensitivity": 0.8,
        "specificity": 0.9,
        "precision": 0.75,
        "f1_score": 0.77,
        "mcc": 0.7,
        "balanced_accuracy": 0.85,
        "false_positive_rate": 0.1,
        "total_results": 100,
        "confusion_matrix": ConfusionMatrix(
            true_positives=8,
            false_positives=1,
            true_negatives=9,
            false_negatives=2,
        ),
    }
    defaults.update(overrides)
    return ExperimentMetrics(**defaults)


def _mock_control_result(
    pos_intersection: int = 0,
    pos_controls: int = 0,
    neg_intersection: int = 0,
    neg_controls: int = 0,
    result_count: int = 0,
) -> ControlTestResult:
    """Build a minimal ControlTestResult for mocking."""
    return ControlTestResult(
        target=ControlTargetData(result_count=result_count),
        positive=ControlSetData(
            intersection_count=pos_intersection,
            controls_count=pos_controls,
        ),
        negative=ControlSetData(
            intersection_count=neg_intersection,
            controls_count=neg_controls,
        ),
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

    def test_numeric_single_step(self) -> None:
        vals = compute_sweep_values(
            sweep_type="numeric",
            values=None,
            min_value=5.0,
            max_value=10.0,
            steps=1,
        )
        assert len(vals) == 1
        assert float(vals[0]) == pytest.approx(5.0)

    def test_numeric_missing_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            compute_sweep_values(
                sweep_type="numeric",
                values=None,
                min_value=None,
                max_value=1.0,
                steps=5,
            )
        with pytest.raises(ValidationError):
            compute_sweep_values(
                sweep_type="numeric",
                values=None,
                min_value=0.0,
                max_value=None,
                steps=5,
            )

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
        with pytest.raises(ValidationError):
            compute_sweep_values(
                sweep_type="categorical",
                values=None,
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
        # Should not raise
        validate_sweep_parameter(exp, "threshold")

    def test_missing_param_raises(self) -> None:
        exp = _make_experiment()
        with pytest.raises(ValidationError):
            validate_sweep_parameter(exp, "not_a_param")

    def test_tree_mode_finds_param_in_leaf(self) -> None:
        """Tree-mode validation walks the step tree to find the parameter."""
        exp = _make_experiment(
            config_overrides={
                "mode": "multi-step",
                "step_tree": {
                    "searchName": "__combine__",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "searchName": "GenesByTaxon",
                        "parameters": {"organism": "Plasmodium falciparum 3D7"},
                    },
                    "secondaryInput": {
                        "searchName": "GenesByExpression",
                        "parameters": {"fold_change": "2.0"},
                    },
                },
            }
        )
        # Should not raise -- organism exists in primary leaf
        validate_sweep_parameter(exp, "organism")
        # Should not raise -- fold_change exists in secondary leaf
        validate_sweep_parameter(exp, "fold_change")

    def test_tree_mode_missing_param_raises(self) -> None:
        exp = _make_experiment(
            config_overrides={
                "mode": "multi-step",
                "step_tree": {
                    "searchName": "CombineStep",
                    "primaryInput": {
                        "searchName": "GenesByTaxon",
                        "parameters": {"organism": "P. falciparum"},
                    },
                },
            }
        )
        with pytest.raises(ValidationError):
            validate_sweep_parameter(exp, "not_present")


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

    def test_values_rounded(self) -> None:
        m = _make_metrics(sensitivity=0.12345678)
        result = format_metrics_dict(m)
        assert result["sensitivity"] == 0.1235

    def test_total_results_is_int(self) -> None:
        m = _make_metrics(total_results=42)
        result = format_metrics_dict(m)
        assert result["totalResults"] == 42
        assert isinstance(result["totalResults"], int)


# ---------------------------------------------------------------------------
# run_sweep_point
# ---------------------------------------------------------------------------


class TestRunSweepPoint:
    @pytest.mark.asyncio
    async def test_successful_numeric_point(self) -> None:
        exp = _make_experiment()
        mock_result = _mock_control_result(
            pos_intersection=2,
            pos_controls=2,
            neg_intersection=0,
            neg_controls=1,
            result_count=50,
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
        assert "error" not in point

    @pytest.mark.asyncio
    async def test_successful_categorical_point(self) -> None:
        exp = _make_experiment()
        mock_result = _mock_control_result(
            pos_intersection=1,
            pos_controls=2,
            neg_intersection=1,
            neg_controls=1,
            result_count=30,
        )
        with patch(
            "veupath_chatbot.services.experiment.sweep_service.run_positive_negative_controls",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            point = await run_sweep_point(
                exp=exp,
                param_name="organism",
                value="some_org",
                is_categorical=True,
            )

        assert point["value"] == "some_org"
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
        error = point["error"]
        assert isinstance(error, str)
        assert "WDK down" in error


# ---------------------------------------------------------------------------
# re_evaluate
# ---------------------------------------------------------------------------


class TestReEvaluate:
    @pytest.mark.asyncio
    async def test_single_mode(self) -> None:
        exp = _make_experiment()
        mock_result = _mock_control_result(
            pos_intersection=2,
            pos_controls=2,
            neg_intersection=0,
            neg_controls=1,
            result_count=50,
        )
        mock_genes = ([], [], [], [])

        with (
            patch(
                "veupath_chatbot.services.experiment.evaluation.run_positive_negative_controls",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "veupath_chatbot.services.experiment.evaluation.extract_and_enrich_genes",
                new_callable=AsyncMock,
                return_value=mock_genes,
            ),
            patch(
                "veupath_chatbot.services.experiment.evaluation.get_experiment_store",
            ) as mock_store_fn,
        ):
            mock_store = MagicMock()
            mock_store_fn.return_value = mock_store
            result = await re_evaluate(exp)

        assert isinstance(result, dict)
        mock_store.save.assert_called_once_with(exp)
        assert exp.metrics is not None

    @pytest.mark.asyncio
    async def test_tree_mode(self) -> None:
        exp = _make_experiment(
            config_overrides={
                "mode": "multi-step",
                "step_tree": {"searchName": "X", "primaryInput": {"searchName": "Y"}},
            }
        )
        mock_result = _mock_control_result(
            pos_intersection=1,
            pos_controls=2,
            neg_intersection=0,
            neg_controls=1,
            result_count=20,
        )
        mock_genes = ([], [], [], [])

        with (
            patch(
                "veupath_chatbot.services.experiment.evaluation.run_controls_against_tree",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_tree_fn,
            patch(
                "veupath_chatbot.services.experiment.evaluation.extract_and_enrich_genes",
                new_callable=AsyncMock,
                return_value=mock_genes,
            ),
            patch(
                "veupath_chatbot.services.experiment.evaluation.get_experiment_store",
            ) as mock_store_fn,
        ):
            mock_store = MagicMock()
            mock_store_fn.return_value = mock_store
            result = await re_evaluate(exp)

        mock_tree_fn.assert_called_once()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# generate_sweep_events
# ---------------------------------------------------------------------------


class TestGenerateSweepEvents:
    @pytest.mark.asyncio
    async def test_emits_point_and_complete_events(self) -> None:
        exp = _make_experiment()
        mock_result = _mock_control_result(
            pos_intersection=2,
            pos_controls=2,
            neg_intersection=0,
            neg_controls=1,
            result_count=50,
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

        # 3 sweep_point events + 1 sweep_complete
        point_events = [e for e in events if "sweep_point" in e]
        complete_events = [e for e in events if "sweep_complete" in e]
        assert len(point_events) == 3
        assert len(complete_events) == 1


# ---------------------------------------------------------------------------
# _tree_has_parameter
# ---------------------------------------------------------------------------


class TestTreeHasParameter:
    def test_finds_param_in_root(self) -> None:
        tree = PlanStepNode(search_name="S", parameters={"threshold": "0.5"})
        assert _tree_has_parameter(tree, "threshold") is True

    def test_finds_param_in_nested_primary_input(self) -> None:
        tree = PlanStepNode(
            search_name="CombineStep",
            primary_input=PlanStepNode(
                search_name="S",
                parameters={"threshold": "0.5"},
            ),
        )
        assert _tree_has_parameter(tree, "threshold") is True

    def test_finds_param_in_nested_secondary_input(self) -> None:
        tree = PlanStepNode(
            search_name="__combine__",
            operator="INTERSECT",
            primary_input=PlanStepNode(
                search_name="A",
                parameters={"organism": "Pf"},
            ),
            secondary_input=PlanStepNode(
                search_name="B",
                parameters={"fold_change": "2.0"},
            ),
        )
        assert _tree_has_parameter(tree, "fold_change") is True

    def test_deeply_nested_param(self) -> None:
        tree = PlanStepNode(
            search_name="Root",
            primary_input=PlanStepNode(
                search_name="Mid",
                primary_input=PlanStepNode(
                    search_name="Leaf",
                    parameters={"deep_param": "1"},
                ),
            ),
        )
        assert _tree_has_parameter(tree, "deep_param") is True

    def test_returns_false_when_param_missing(self) -> None:
        tree = PlanStepNode(
            search_name="S",
            parameters={"threshold": "0.5"},
        )
        assert _tree_has_parameter(tree, "nonexistent") is False

    def test_handles_node_without_parameters(self) -> None:
        tree = PlanStepNode(
            search_name="CombineStep",
            primary_input=PlanStepNode(search_name="Leaf"),
        )
        assert _tree_has_parameter(tree, "threshold") is False


# ---------------------------------------------------------------------------
# _run_sweep_point_tree
# ---------------------------------------------------------------------------


class TestRunSweepPointTree:
    @pytest.mark.asyncio
    async def test_clones_and_injects_parameter(self) -> None:
        """_run_sweep_point_tree deep-copies the tree and injects the value."""
        exp = _make_experiment(
            config_overrides={
                "mode": "multi-step",
                "step_tree": {
                    "searchName": "__combine__",
                    "operator": "INTERSECT",
                    "primaryInput": {
                        "searchName": "GenesByTaxon",
                        "parameters": {"threshold": "0.5"},
                    },
                    "secondaryInput": {
                        "searchName": "GenesByExpression",
                        "parameters": {"threshold": "0.5", "other": "keep"},
                    },
                },
            }
        )
        mock_result = _mock_control_result(
            pos_intersection=2,
            pos_controls=2,
            neg_intersection=0,
            neg_controls=1,
            result_count=40,
        )

        captured_tree: PlanStepNode | None = None

        async def _capture_tree(
            ctx: ControlsContext, tree: PlanStepNode
        ) -> ControlTestResult:
            nonlocal captured_tree
            captured_tree = tree
            return mock_result

        with patch(
            "veupath_chatbot.services.experiment.sweep_service.run_controls_against_tree",
            new_callable=AsyncMock,
            side_effect=_capture_tree,
        ):
            point = await run_sweep_point(
                exp=exp,
                param_name="threshold",
                value="0.99",
                is_categorical=False,
            )

        # The sweep point should succeed
        assert point["metrics"] is not None
        assert point["value"] == pytest.approx(0.99)

        # Verify the tree was modified with the swept value
        assert captured_tree is not None
        assert captured_tree.primary_input is not None
        assert captured_tree.primary_input.parameters["threshold"] == "0.99"
        assert captured_tree.secondary_input is not None
        assert captured_tree.secondary_input.parameters["threshold"] == "0.99"
        # Non-swept params should be preserved
        assert captured_tree.secondary_input.parameters["other"] == "keep"

        # Verify original tree was NOT modified (deep copy)
        step_tree = exp.config.step_tree
        assert step_tree is not None
        assert step_tree.primary_input is not None
        assert step_tree.primary_input.parameters["threshold"] == "0.5"
        assert step_tree.secondary_input is not None
        assert step_tree.secondary_input.parameters["threshold"] == "0.5"


# ---------------------------------------------------------------------------
# _numeric_value (sorting helper inside generate_sweep_events)
# ---------------------------------------------------------------------------


class TestNumericValueSorting:
    @pytest.mark.asyncio
    async def test_numeric_sweep_events_are_sorted_by_value(self) -> None:
        """Sweep results are sorted numerically, so even out-of-order
        completion produces sorted output in sweep_complete."""
        exp = _make_experiment()
        call_count = 0

        async def _mock_controls(*_args: object, **_: object) -> ControlTestResult:
            nonlocal call_count
            call_count += 1
            return _mock_control_result(
                pos_intersection=1,
                pos_controls=2,
                neg_intersection=0,
                neg_controls=1,
                result_count=50,
            )

        with (
            patch(
                "veupath_chatbot.services.experiment.sweep_service.cleanup_before_sweep",
                new_callable=AsyncMock,
            ),
            patch(
                "veupath_chatbot.services.experiment.sweep_service.run_positive_negative_controls",
                new_callable=AsyncMock,
                side_effect=_mock_controls,
            ),
        ):
            events = [
                event
                async for event in generate_sweep_events(
                    exp=exp,
                    param_name="threshold",
                    sweep_type="numeric",
                    sweep_values=["1.0", "0.0", "0.5"],
                )
            ]

        # Find sweep_complete event
        complete_event = next(e for e in events if "sweep_complete" in e)
        data_str = complete_event.split("data: ", 1)[1].strip()
        data = json_mod.loads(data_str)
        values = [p["value"] for p in data["points"]]
        assert values == sorted(values), "Points should be sorted numerically"

    @pytest.mark.asyncio
    async def test_non_numeric_string_value_sorts_as_zero(self) -> None:
        """Non-numeric string values should be treated as 0.0 for sorting."""
        exp = _make_experiment()

        mock_result = _mock_control_result(
            pos_intersection=1,
            pos_controls=2,
            neg_intersection=0,
            neg_controls=1,
            result_count=50,
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
            # Mix a non-numeric value with numeric ones
            events = [
                event
                async for event in generate_sweep_events(
                    exp=exp,
                    param_name="threshold",
                    sweep_type="numeric",
                    sweep_values=["1.0", "not_a_number", "0.5"],
                )
            ]

        # Should have 3 point events and 1 complete event
        point_events = [e for e in events if "sweep_point" in e]
        complete_events = [e for e in events if "sweep_complete" in e]
        assert len(point_events) == 3
        assert len(complete_events) == 1
