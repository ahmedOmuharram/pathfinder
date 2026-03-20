"""Tests for OptimizationToolsMixin — parameter validation and JSON parsing.

The optimize_search_parameters tool has extensive input validation before
it delegates to the optimization service. These tests exercise every
validation branch without calling the actual optimization engine.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from veupath_chatbot.ai.tools.planner.optimization_tools import OptimizationToolsMixin
from veupath_chatbot.services.parameter_optimization import (
    OptimizationResult,
    TrialResult,
)

_SITE_ID = "plasmodb"


class _TestableTools(OptimizationToolsMixin):
    """Concrete subclass for testing."""

    def __init__(self, site_id: str = _SITE_ID) -> None:
        self.site_id = site_id
        self._events: list[object] = []

    async def _emit_event(self, event: object) -> None:
        self._events.append(event)


def _valid_kwargs() -> dict[str, object]:
    """Return a minimal set of valid keyword arguments."""
    return {
        "record_type": "gene",
        "search_name": "GenesByFoldChange",
        "parameter_space_json": json.dumps(
            [{"name": "fold_change", "type": "numeric", "min": 1.5, "max": 20.0}]
        ),
        "fixed_parameters_json": json.dumps({"organism": "P. falciparum 3D7"}),
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "positive_controls": ["PF3D7_0100100"],
    }


def _parse_error(result: str) -> str:
    """Parse an error JSON string and return the error message."""
    data = json.loads(result)
    return data["error"]


# ---------------------------------------------------------------------------
# Scalar argument validation
# ---------------------------------------------------------------------------


class TestRecordTypeValidation:
    async def test_empty_record_type_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["record_type"] = ""
        result = await tools.optimize_search_parameters(**kwargs)
        assert "record_type is required" in _parse_error(result)

    async def test_whitespace_record_type_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["record_type"] = "   "
        result = await tools.optimize_search_parameters(**kwargs)
        assert "record_type is required" in _parse_error(result)


class TestSearchNameValidation:
    async def test_empty_search_name_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["search_name"] = ""
        result = await tools.optimize_search_parameters(**kwargs)
        assert "search_name is required" in _parse_error(result)


class TestControlsSearchNameValidation:
    async def test_empty_controls_search_name_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["controls_search_name"] = ""
        result = await tools.optimize_search_parameters(**kwargs)
        assert "controls_search_name is required" in _parse_error(result)


class TestControlsParamNameValidation:
    async def test_empty_controls_param_name_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["controls_param_name"] = ""
        result = await tools.optimize_search_parameters(**kwargs)
        assert "controls_param_name is required" in _parse_error(result)


class TestControlsRequirement:
    async def test_no_controls_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["positive_controls"] = None
        kwargs["negative_controls"] = None
        result = await tools.optimize_search_parameters(**kwargs)
        assert "At least one of positive_controls or negative_controls" in _parse_error(
            result
        )

    async def test_empty_controls_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["positive_controls"] = []
        kwargs["negative_controls"] = []
        result = await tools.optimize_search_parameters(**kwargs)
        assert "At least one of positive_controls or negative_controls" in _parse_error(
            result
        )

    async def test_only_positive_controls_is_valid(self) -> None:
        """Having only positive controls (no negatives) should pass validation."""
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["positive_controls"] = ["g1"]
        kwargs["negative_controls"] = None

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            # Set up a mock return value
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            result = await tools.optimize_search_parameters(**kwargs)

        # Should not be an error
        parsed = json.loads(result)
        assert "error" not in parsed

    async def test_only_negative_controls_is_valid(self) -> None:
        """Having only negative controls (no positives) should pass validation."""
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["positive_controls"] = None
        kwargs["negative_controls"] = ["n1"]

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            result = await tools.optimize_search_parameters(**kwargs)

        parsed = json.loads(result)
        assert "error" not in parsed


class TestObjectiveValidation:
    async def test_invalid_objective_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["objective"] = "invalid_obj"
        result = await tools.optimize_search_parameters(**kwargs)
        assert "Invalid objective" in _parse_error(result)

    async def test_valid_objectives_accepted(self) -> None:
        for obj in ("f1", "f_beta", "recall", "precision", "custom"):
            tools = _TestableTools()
            kwargs = _valid_kwargs()
            kwargs["objective"] = obj
            # Should pass objective validation (may fail later at optimization call)
            with patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
                new_callable=AsyncMock,
            ) as mock_opt:
                mock_opt.return_value = OptimizationResult(
                    optimization_id="test",
                    best_trial=TrialResult(
                        trial_number=1,
                        parameters={},
                        score=0.5,
                        recall=0.5,
                        false_positive_rate=0.0,
                        result_count=10,
                    ),
                    all_trials=[],
                    pareto_frontier=[],
                    sensitivity={},
                    total_time_seconds=1.0,
                    status="completed",
                )
                result = await tools.optimize_search_parameters(**kwargs)
            parsed = json.loads(result)
            assert "error" not in parsed, f"Objective '{obj}' should be valid"


class TestMethodValidation:
    async def test_invalid_method_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["method"] = "evolution"
        result = await tools.optimize_search_parameters(**kwargs)
        assert "Invalid method" in _parse_error(result)

    async def test_valid_methods_accepted(self) -> None:
        for method in ("bayesian", "grid", "random"):
            tools = _TestableTools()
            kwargs = _valid_kwargs()
            kwargs["method"] = method
            with patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
                new_callable=AsyncMock,
            ) as mock_opt:
                mock_opt.return_value = OptimizationResult(
                    optimization_id="test",
                    best_trial=TrialResult(
                        trial_number=1,
                        parameters={},
                        score=0.5,
                        recall=0.5,
                        false_positive_rate=0.0,
                        result_count=10,
                    ),
                    all_trials=[],
                    pareto_frontier=[],
                    sensitivity={},
                    total_time_seconds=1.0,
                    status="completed",
                )
                result = await tools.optimize_search_parameters(**kwargs)
            parsed = json.loads(result)
            assert "error" not in parsed, f"Method '{method}' should be valid"


class TestControlsValueFormatValidation:
    async def test_invalid_format_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["controls_value_format"] = "tsv"
        result = await tools.optimize_search_parameters(**kwargs)
        assert "Invalid controls_value_format" in _parse_error(result)


class TestBudgetValidation:
    async def test_zero_budget_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["budget"] = 0
        result = await tools.optimize_search_parameters(**kwargs)
        assert "budget must be a positive integer" in _parse_error(result)

    async def test_negative_budget_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["budget"] = -1
        result = await tools.optimize_search_parameters(**kwargs)
        assert "budget must be a positive integer" in _parse_error(result)

    async def test_budget_over_50_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["budget"] = 51
        result = await tools.optimize_search_parameters(**kwargs)
        assert "exceeds the maximum of 50" in _parse_error(result)

    async def test_budget_exactly_50_is_valid(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["budget"] = 50
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            result = await tools.optimize_search_parameters(**kwargs)

        parsed = json.loads(result)
        assert "error" not in parsed


class TestBetaValidation:
    async def test_invalid_beta_with_f_beta_objective(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["objective"] = "f_beta"
        kwargs["beta"] = 0
        result = await tools.optimize_search_parameters(**kwargs)
        assert "beta must be a positive number" in _parse_error(result)

    async def test_negative_beta_with_f_beta_objective(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["objective"] = "f_beta"
        kwargs["beta"] = -1.0
        result = await tools.optimize_search_parameters(**kwargs)
        assert "beta must be a positive number" in _parse_error(result)


# ---------------------------------------------------------------------------
# JSON argument parsing & validation
# ---------------------------------------------------------------------------


class TestParameterSpaceJsonParsing:
    async def test_invalid_json_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = "not valid json {"
        result = await tools.optimize_search_parameters(**kwargs)
        assert "parameter_space_json is not valid JSON" in _parse_error(result)

    async def test_non_array_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps({"name": "fold_change"})
        result = await tools.optimize_search_parameters(**kwargs)
        assert "must be a JSON array" in _parse_error(result)

    async def test_empty_array_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps([])
        result = await tools.optimize_search_parameters(**kwargs)
        assert "empty array" in _parse_error(result)


class TestFixedParametersJsonParsing:
    async def test_invalid_json_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["fixed_parameters_json"] = "bad json"
        result = await tools.optimize_search_parameters(**kwargs)
        assert "fixed_parameters_json is not valid JSON" in _parse_error(result)

    async def test_non_object_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["fixed_parameters_json"] = json.dumps(["a", "b"])
        result = await tools.optimize_search_parameters(**kwargs)
        assert "must be a JSON object" in _parse_error(result)

    async def test_empty_string_becomes_empty_dict(self) -> None:
        """Empty fixed_parameters_json should default to {}."""
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["fixed_parameters_json"] = ""
        # Should pass JSON parsing (empty string -> {})
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            result = await tools.optimize_search_parameters(**kwargs)

        parsed = json.loads(result)
        assert "error" not in parsed
        # Verify empty dict was passed to optimizer
        call_kwargs = mock_opt.call_args.kwargs
        assert call_kwargs["fixed_parameters"] == {}


class TestControlsExtraParametersJsonParsing:
    async def test_invalid_json_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["controls_extra_parameters_json"] = "bad json"
        result = await tools.optimize_search_parameters(**kwargs)
        assert "controls_extra_parameters_json is not valid JSON" in _parse_error(
            result
        )

    async def test_non_object_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["controls_extra_parameters_json"] = json.dumps([1, 2])
        result = await tools.optimize_search_parameters(**kwargs)
        assert "must be a JSON object" in _parse_error(result)


# ---------------------------------------------------------------------------
# Parameter space entry validation
# ---------------------------------------------------------------------------


class TestParameterSpaceEntryValidation:
    async def test_non_object_entry_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(["not_an_object"])
        result = await tools.optimize_search_parameters(**kwargs)
        assert "must be an object" in _parse_error(result)

    async def test_missing_name_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"type": "numeric", "min": 0, "max": 10}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "missing a 'name'" in _parse_error(result)

    async def test_duplicate_names_return_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [
                {"name": "fold_change", "type": "numeric", "min": 1, "max": 10},
                {"name": "fold_change", "type": "numeric", "min": 2, "max": 20},
            ]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "duplicate parameter name" in _parse_error(result)

    async def test_invalid_type_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fold_change", "type": "float", "min": 1, "max": 10}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "invalid type" in _parse_error(result)


class TestNumericParameterValidation:
    async def test_missing_min_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "max": 10}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "requires both 'min' and 'max'" in _parse_error(result)

    async def test_missing_max_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": 1}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "requires both 'min' and 'max'" in _parse_error(result)

    async def test_min_equals_max_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": 5, "max": 5}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "must be strictly less than" in _parse_error(result)

    async def test_min_greater_than_max_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": 20, "max": 5}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "must be strictly less than" in _parse_error(result)

    async def test_non_numeric_min_max_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": "abc", "max": 10}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "'min' and 'max' must be numbers" in _parse_error(result)

    async def test_negative_step_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": 1, "max": 10, "step": -1}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "'step' must be positive" in _parse_error(result)

    async def test_zero_step_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": 1, "max": 10, "step": 0}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "'step' must be positive" in _parse_error(result)

    async def test_non_numeric_step_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "fc", "type": "numeric", "min": 1, "max": 10, "step": "abc"}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "'step' must be a number" in _parse_error(result)


class TestIntegerParameterValidation:
    async def test_missing_min_max_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "count", "type": "integer", "min": 1}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "requires both 'min' and 'max'" in _parse_error(result)


class TestCategoricalParameterValidation:
    async def test_missing_choices_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "direction", "type": "categorical"}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "non-empty 'choices' array" in _parse_error(result)

    async def test_empty_choices_returns_error(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [{"name": "direction", "type": "categorical", "choices": []}]
        )
        result = await tools.optimize_search_parameters(**kwargs)
        assert "non-empty 'choices' array" in _parse_error(result)


# ---------------------------------------------------------------------------
# Successful delegation to optimizer
# ---------------------------------------------------------------------------


class TestSuccessfulOptimization:
    async def test_builds_correct_parameter_specs(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["parameter_space_json"] = json.dumps(
            [
                {
                    "name": "fold_change",
                    "type": "numeric",
                    "min": 1.5,
                    "max": 20.0,
                    "logScale": True,
                    "step": 0.5,
                },
                {"name": "direction", "type": "categorical", "choices": ["up", "down"]},
                {"name": "count", "type": "integer", "min": 1, "max": 100},
            ]
        )

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            await tools.optimize_search_parameters(**kwargs)

        call_kwargs = mock_opt.call_args.kwargs
        specs = call_kwargs["parameter_space"]
        assert len(specs) == 3

        # Numeric spec
        assert specs[0].name == "fold_change"
        assert specs[0].param_type == "numeric"
        assert specs[0].min_value == 1.5
        assert specs[0].max_value == 20.0
        assert specs[0].log_scale is True
        assert specs[0].step == 0.5

        # Categorical spec
        assert specs[1].name == "direction"
        assert specs[1].param_type == "categorical"
        assert specs[1].choices == ["up", "down"]

        # Integer spec
        assert specs[2].name == "count"
        assert specs[2].param_type == "integer"
        assert specs[2].min_value == 1.0
        assert specs[2].max_value == 100.0

    async def test_builds_correct_config(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["budget"] = 25
        kwargs["objective"] = "f_beta"
        kwargs["beta"] = 2.0
        kwargs["method"] = "grid"
        kwargs["result_count_penalty"] = 0.5

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            await tools.optimize_search_parameters(**kwargs)

        call_kwargs = mock_opt.call_args.kwargs
        config = call_kwargs["config"]
        assert config.budget == 25
        assert config.objective == "f_beta"
        assert config.beta == 2.0
        assert config.method == "grid"
        assert config.result_count_penalty == 0.5

    async def test_result_count_penalty_cannot_be_negative(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["result_count_penalty"] = -0.5

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            await tools.optimize_search_parameters(**kwargs)

        call_kwargs = mock_opt.call_args.kwargs
        config = call_kwargs["config"]
        assert config.result_count_penalty == 0.0  # max(0.0, -0.5)

    async def test_passes_controls_extra_parameters(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()
        kwargs["controls_extra_parameters_json"] = json.dumps(
            {"organism": "P. falciparum 3D7"}
        )

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            await tools.optimize_search_parameters(**kwargs)

        call_kwargs = mock_opt.call_args.kwargs
        assert call_kwargs["controls_extra_parameters"] == {
            "organism": "P. falciparum 3D7"
        }

    async def test_returns_json_string(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()

        with (
            patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
                new_callable=AsyncMock,
            ) as mock_opt,
            patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools._opt_result_to_json",
                return_value={"best": {"score": 0.9}},
            ),
        ):
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.9,
                    recall=0.9,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            result = await tools.optimize_search_parameters(**kwargs)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["best"] == {"score": 0.9}
        assert "downloads" in parsed
        assert parsed["downloads"]["expiresInSeconds"] == 600
        assert parsed["downloads"]["json"].startswith("/api/v1/exports/")

    async def test_cancel_event_passed_when_present(self) -> None:
        tools = _TestableTools()
        tools._cancel_event = asyncio.Event()
        kwargs = _valid_kwargs()

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            await tools.optimize_search_parameters(**kwargs)

        call_kwargs = mock_opt.call_args.kwargs
        assert call_kwargs["check_cancelled"] is not None

    async def test_cancel_event_none_when_absent(self) -> None:
        tools = _TestableTools()
        kwargs = _valid_kwargs()

        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools._run_optimization",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = OptimizationResult(
                optimization_id="test",
                best_trial=TrialResult(
                    trial_number=1,
                    parameters={},
                    score=0.5,
                    recall=0.5,
                    false_positive_rate=0.0,
                    result_count=10,
                ),
                all_trials=[],
                pareto_frontier=[],
                sensitivity={},
                total_time_seconds=1.0,
                status="completed",
            )
            await tools.optimize_search_parameters(**kwargs)

        call_kwargs = mock_opt.call_args.kwargs
        assert call_kwargs["check_cancelled"] is None
