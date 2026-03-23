"""Tests for OptimizationToolsMixin — parameter validation and JSON parsing.

The optimize_search_parameters tool has extensive input validation before
it delegates to the optimization service. These tests exercise every
validation branch without calling the actual optimization engine.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from veupath_chatbot.ai.tools.planner.optimization_tools import (
    OptimizationControls,
    OptimizationSettings,
    OptimizationTarget,
    OptimizationToolsMixin,
)
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


def _valid_target(**overrides: object) -> OptimizationTarget:
    """Build a minimal valid OptimizationTarget, with optional overrides."""
    defaults: dict[str, object] = {
        "record_type": "gene",
        "search_name": "GenesByFoldChange",
        "parameter_space_json": json.dumps(
            [{"name": "fold_change", "type": "numeric", "min": 1.5, "max": 20.0}]
        ),
        "fixed_parameters_json": json.dumps({"organism": "P. falciparum 3D7"}),
    }
    defaults.update(overrides)
    return OptimizationTarget(**defaults)  # type: ignore[arg-type]


def _valid_controls(**overrides: object) -> OptimizationControls:
    """Build a minimal valid OptimizationControls, with optional overrides."""
    defaults: dict[str, object] = {
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "positive_controls": ["PF3D7_0100100"],
    }
    defaults.update(overrides)
    return OptimizationControls(**defaults)  # type: ignore[arg-type]


def _valid_settings(**overrides: object) -> OptimizationSettings:
    """Build valid OptimizationSettings, with optional overrides."""
    defaults: dict[str, object] = {}
    defaults.update(overrides)
    return OptimizationSettings(**defaults)  # type: ignore[arg-type]


def _parse_error(result: str) -> str:
    """Parse an error JSON string and return the error message."""
    data = json.loads(result)
    return data["error"]


def _mock_opt_result() -> OptimizationResult:
    """Build a minimal successful OptimizationResult for mocking."""
    return OptimizationResult(
        optimization_id="test",
        best_trial=TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.5,
            false_positive_rate=0.0,
            estimated_size=10,
        ),
        all_trials=[],
        pareto_frontier=[],
        sensitivity={},
        total_time_seconds=1.0,
        status="completed",
    )


class TestControlsRequirement:
    def test_no_controls_raises(self) -> None:
        with pytest.raises(ValidationError):
            _valid_controls(positive_controls=None, negative_controls=None)

    def test_empty_controls_raises(self) -> None:
        with pytest.raises(ValidationError):
            _valid_controls(positive_controls=[], negative_controls=[])

    async def test_only_positive_controls_is_valid(self) -> None:
        """Having only positive controls (no negatives) should pass validation."""
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            result = await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(
                    positive_controls=["g1"], negative_controls=None
                ),
            )

        # Should not be an error
        parsed = json.loads(result)
        assert "error" not in parsed

    async def test_only_negative_controls_is_valid(self) -> None:
        """Having only negative controls (no positives) should pass validation."""
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            result = await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(
                    positive_controls=None, negative_controls=["n1"]
                ),
            )

        parsed = json.loads(result)
        assert "error" not in parsed


class TestObjectiveValidation:
    async def test_valid_objectives_accepted(self) -> None:
        for obj in ("f1", "f_beta", "recall", "precision", "custom"):
            tools = _TestableTools()
            with patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
                new_callable=AsyncMock,
            ) as mock_opt:
                mock_opt.return_value = _mock_opt_result()
                result = await tools.optimize_search_parameters(
                    target=_valid_target(),
                    controls=_valid_controls(),
                    settings=_valid_settings(objective=obj),
                )
            parsed = json.loads(result)
            assert "error" not in parsed, f"Objective '{obj}' should be valid"


class TestMethodValidation:
    async def test_valid_methods_accepted(self) -> None:
        for method in ("bayesian", "grid", "random"):
            tools = _TestableTools()
            with patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
                new_callable=AsyncMock,
            ) as mock_opt:
                mock_opt.return_value = _mock_opt_result()
                result = await tools.optimize_search_parameters(
                    target=_valid_target(),
                    controls=_valid_controls(),
                    settings=_valid_settings(method=method),
                )
            parsed = json.loads(result)
            assert "error" not in parsed, f"Method '{method}' should be valid"


class TestBudgetValidation:
    async def test_budget_exactly_50_is_valid(self) -> None:
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            result = await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(),
                settings=_valid_settings(budget=50),
            )

        parsed = json.loads(result)
        assert "error" not in parsed


class TestBetaValidation:
    def test_invalid_beta_raises(self) -> None:
        with pytest.raises(ValidationError):
            _valid_settings(objective="f_beta", beta=0)

    def test_negative_beta_raises(self) -> None:
        with pytest.raises(ValidationError):
            _valid_settings(objective="f_beta", beta=-1.0)


class TestParameterSpaceJsonParsing:
    async def test_invalid_json_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(parameter_space_json="not valid json {"),
            controls=_valid_controls(),
        )
        error = _parse_error(result)
        assert error

    async def test_non_array_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps({"name": "fold_change"})
            ),
            controls=_valid_controls(),
        )
        error = _parse_error(result)
        assert error

    async def test_empty_array_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(parameter_space_json=json.dumps([])),
            controls=_valid_controls(),
        )
        assert "empty" in _parse_error(result)


class TestFixedParametersJsonParsing:
    async def test_invalid_json_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(fixed_parameters_json="bad json"),
            controls=_valid_controls(),
        )
        error = _parse_error(result)
        assert error

    async def test_non_object_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(fixed_parameters_json=json.dumps(["a", "b"])),
            controls=_valid_controls(),
        )
        error = _parse_error(result)
        assert error

    async def test_empty_string_becomes_empty_dict(self) -> None:
        """Empty fixed_parameters_json should default to {}."""
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            result = await tools.optimize_search_parameters(
                target=_valid_target(fixed_parameters_json=""),
                controls=_valid_controls(),
            )

        parsed = json.loads(result)
        assert "error" not in parsed
        # Verify empty dict was passed to optimizer
        inp = mock_opt.call_args.args[0]
        assert inp.fixed_parameters == {}


class TestControlsExtraParametersJsonParsing:
    async def test_invalid_json_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(),
            controls=_valid_controls(controls_extra_parameters_json="bad json"),
        )
        error = _parse_error(result)
        assert error

    async def test_non_object_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(),
            controls=_valid_controls(controls_extra_parameters_json=json.dumps([1, 2])),
        )
        error = _parse_error(result)
        assert error


class TestParameterSpaceEntryValidation:
    async def test_duplicate_names_return_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [
                        {"name": "fold_change", "type": "numeric", "min": 1, "max": 10},
                        {"name": "fold_change", "type": "numeric", "min": 2, "max": 20},
                    ]
                )
            ),
            controls=_valid_controls(),
        )
        assert "Duplicate" in _parse_error(result)


class TestNumericParameterValidation:
    async def test_missing_min_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "fc", "type": "numeric", "max": 10}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "requires both 'min' and 'max'" in _parse_error(result)

    async def test_missing_max_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "fc", "type": "numeric", "min": 1}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "requires both 'min' and 'max'" in _parse_error(result)

    async def test_min_equals_max_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "fc", "type": "numeric", "min": 5, "max": 5}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "must be strictly less than" in _parse_error(result)

    async def test_min_greater_than_max_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "fc", "type": "numeric", "min": 20, "max": 5}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "must be strictly less than" in _parse_error(result)

    async def test_negative_step_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "fc", "type": "numeric", "min": 1, "max": 10, "step": -1}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "'step' must be positive" in _parse_error(result)

    async def test_zero_step_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "fc", "type": "numeric", "min": 1, "max": 10, "step": 0}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "'step' must be positive" in _parse_error(result)


class TestIntegerParameterValidation:
    async def test_missing_min_max_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "count", "type": "integer", "min": 1}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "requires both 'min' and 'max'" in _parse_error(result)


class TestCategoricalParameterValidation:
    async def test_missing_choices_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "direction", "type": "categorical"}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "non-empty 'choices' array" in _parse_error(result)

    async def test_empty_choices_returns_error(self) -> None:
        tools = _TestableTools()
        result = await tools.optimize_search_parameters(
            target=_valid_target(
                parameter_space_json=json.dumps(
                    [{"name": "direction", "type": "categorical", "choices": []}]
                )
            ),
            controls=_valid_controls(),
        )
        assert "non-empty 'choices' array" in _parse_error(result)


class TestSuccessfulOptimization:
    async def test_builds_correct_parameter_specs(self) -> None:
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            await tools.optimize_search_parameters(
                target=_valid_target(
                    parameter_space_json=json.dumps(
                        [
                            {
                                "name": "fold_change",
                                "type": "numeric",
                                "min": 1.5,
                                "max": 20.0,
                                "logScale": True,
                                "step": 0.5,
                            },
                            {
                                "name": "direction",
                                "type": "categorical",
                                "choices": ["up", "down"],
                            },
                            {"name": "count", "type": "integer", "min": 1, "max": 100},
                        ]
                    )
                ),
                controls=_valid_controls(),
            )

        inp = mock_opt.call_args.args[0]
        specs = inp.parameter_space
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
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(),
                settings=_valid_settings(
                    budget=25,
                    objective="f_beta",
                    beta=2.0,
                    method="grid",
                    estimated_size_penalty=0.5,
                ),
            )

        call_kwargs = mock_opt.call_args.kwargs
        config = call_kwargs["config"]
        assert config.budget == 25
        assert config.objective == "f_beta"
        assert config.beta == 2.0
        assert config.method == "grid"
        assert config.estimated_size_penalty == 0.5

    async def test_estimated_size_penalty_cannot_be_negative(self) -> None:
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(),
                settings=_valid_settings(estimated_size_penalty=-0.5),
            )

        call_kwargs = mock_opt.call_args.kwargs
        config = call_kwargs["config"]
        assert config.estimated_size_penalty == 0.0  # max(0.0, -0.5)

    async def test_passes_controls_extra_parameters(self) -> None:
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(
                    controls_extra_parameters_json=json.dumps(
                        {"organism": "P. falciparum 3D7"}
                    )
                ),
            )

        inp = mock_opt.call_args.args[0]
        assert inp.controls_extra_parameters == {"organism": "P. falciparum 3D7"}

    async def test_returns_json_string(self) -> None:
        tools = _TestableTools()
        with (
            patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
                new_callable=AsyncMock,
            ) as mock_opt,
            patch(
                "veupath_chatbot.ai.tools.planner.optimization_tools.result_to_json",
                return_value={"best": {"score": 0.9}},
            ),
        ):
            mock_opt.return_value = _mock_opt_result()
            result = await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(),
            )

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["best"] == {"score": 0.9}
        assert "downloads" in parsed
        assert parsed["downloads"]["expiresInSeconds"] == 600
        assert parsed["downloads"]["json"].startswith("/api/v1/exports/")

    async def test_cancel_event_passed_when_present(self) -> None:
        tools = _TestableTools()
        tools._cancel_event = asyncio.Event()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(),
            )

        call_kwargs = mock_opt.call_args.kwargs
        assert call_kwargs["check_cancelled"] is not None

    async def test_cancel_event_none_when_absent(self) -> None:
        tools = _TestableTools()
        with patch(
            "veupath_chatbot.ai.tools.planner.optimization_tools.optimize_search_parameters",
            new_callable=AsyncMock,
        ) as mock_opt:
            mock_opt.return_value = _mock_opt_result()
            await tools.optimize_search_parameters(
                target=_valid_target(),
                controls=_valid_controls(),
            )

        call_kwargs = mock_opt.call_args.kwargs
        assert call_kwargs["check_cancelled"] is None
