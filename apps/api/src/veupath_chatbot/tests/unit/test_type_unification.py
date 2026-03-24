"""Tests for the unified TrialResult / OptimizationResult CamelModels.

Verifies that:
- TrialResult is a frozen CamelModel that serializes to camelCase with
  RoundedFloat (4 dp) rounding.
- OptimizationResult is a CamelModel that serializes to camelCase with
  a computed total_trials field and RoundedFloat2 (2 dp) for time.
- The old bridge functions are gone; model_dump is all that is needed.
- Callback event models serialize via CamelModel.
"""

import pytest
from pydantic import BaseModel, ValidationError

from veupath_chatbot.services.parameter_optimization import scoring
from veupath_chatbot.services.parameter_optimization.callbacks import (
    OptimizationCompletedEvent,
    OptimizationErrorEvent,
    OptimizationStartedEvent,
    TrialProgressEvent,
)
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationResult,
    TrialResult,
)

# ===================================================================
# TrialResult as CamelModel
# ===================================================================


class TestTrialResultCamelModel:
    """TrialResult should be a frozen CamelModel with RoundedFloat fields."""

    def test_serializes_to_camel_case(self) -> None:
        t = TrialResult(
            trial_number=3,
            parameters={"fc": 2.5},
            score=0.87654,
            recall=0.91234,
            false_positive_rate=0.05678,
            estimated_size=150,
            positive_hits=9,
            negative_hits=1,
            total_positives=10,
            total_negatives=8,
        )
        j = t.model_dump(by_alias=True, mode="json")
        assert j["trialNumber"] == 3
        assert j["parameters"] == {"fc": 2.5}
        # RoundedFloat: 4 dp
        assert j["score"] == round(0.87654, 4)
        assert j["recall"] == round(0.91234, 4)
        assert j["falsePositiveRate"] == round(0.05678, 4)
        assert j["estimatedSize"] == 150
        assert j["positiveHits"] == 9
        assert j["negativeHits"] == 1
        assert j["totalPositives"] == 10
        assert j["totalNegatives"] == 8

    def test_score_rounding_4dp(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.123456789,
            recall=None,
            false_positive_rate=None,
            estimated_size=None,
        )
        j = t.model_dump(by_alias=True, mode="json")
        assert j["score"] == 0.1235

    def test_none_fields_serialized(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=None,
            false_positive_rate=None,
            estimated_size=None,
        )
        j = t.model_dump(by_alias=True, mode="json")
        assert j["recall"] is None
        assert j["falsePositiveRate"] is None
        assert j["estimatedSize"] is None
        assert j["positiveHits"] is None
        assert j["negativeHits"] is None

    def test_frozen(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.8,
            false_positive_rate=0.1,
            estimated_size=100,
        )
        with pytest.raises(ValidationError):
            t.score = 1.0  # type: ignore[misc]

    def test_is_pydantic_model(self) -> None:
        """TrialResult should be a Pydantic BaseModel (CamelModel), not a dataclass."""
        assert issubclass(TrialResult, BaseModel)


# ===================================================================
# OptimizationResult as CamelModel
# ===================================================================


class TestOptimizationResultCamelModel:
    """OptimizationResult should be a CamelModel with computed total_trials."""

    def test_serializes_to_camel_case(self) -> None:
        trial = TrialResult(
            trial_number=1,
            parameters={"fc": 4.0},
            score=0.85,
            recall=0.9,
            false_positive_rate=0.1,
            estimated_size=100,
            positive_hits=9,
            negative_hits=1,
            total_positives=10,
            total_negatives=8,
        )
        result = OptimizationResult(
            optimization_id="test_opt",
            best_trial=trial,
            all_trials=[trial],
            pareto_frontier=[trial],
            sensitivity={"fc": 0.7},
            total_time_seconds=5.567,
            status="completed",
        )
        j = result.model_dump(by_alias=True, mode="json")
        assert j["optimizationId"] == "test_opt"
        assert j["status"] == "completed"
        assert j["totalTrials"] == 1
        # RoundedFloat2: 2 dp
        assert j["totalTimeSeconds"] == 5.57
        assert j["errorMessage"] is None
        best = j["bestTrial"]
        assert isinstance(best, dict)
        assert best["score"] == 0.85

    def test_total_trials_computed_from_all_trials(self) -> None:
        """total_trials should equal len(all_trials)."""
        trials = [
            TrialResult(
                trial_number=i,
                parameters={},
                score=float(i) / 10,
                recall=None,
                false_positive_rate=None,
                estimated_size=None,
            )
            for i in range(1, 6)
        ]
        result = OptimizationResult(
            optimization_id="opt_multi",
            best_trial=trials[-1],
            all_trials=trials,
            pareto_frontier=[],
            sensitivity={},
            total_time_seconds=10.0,
            status="completed",
        )
        j = result.model_dump(by_alias=True, mode="json")
        assert j["totalTrials"] == 5

    def test_none_best_trial(self) -> None:
        result = OptimizationResult(
            optimization_id="test_opt",
            best_trial=None,
            all_trials=[],
            pareto_frontier=[],
            sensitivity={},
            total_time_seconds=1.0,
            status="error",
            error_message="all trials failed",
        )
        j = result.model_dump(by_alias=True, mode="json")
        assert j["bestTrial"] is None
        assert j["errorMessage"] == "all trials failed"
        assert j["totalTrials"] == 0

    def test_is_pydantic_model(self) -> None:
        assert issubclass(OptimizationResult, BaseModel)


# ===================================================================
# No more _trial_to_json / result_to_json bridge functions
# ===================================================================


class TestBridgeFunctionsRemoved:
    """The old bridge functions should not exist in scoring.py anymore."""

    def test_no_trial_to_json(self) -> None:
        assert not hasattr(scoring, "_trial_to_json")

    def test_no_result_to_json(self) -> None:
        assert not hasattr(scoring, "result_to_json")

    def test_no_trial_result_response(self) -> None:
        assert not hasattr(scoring, "TrialResultResponse")

    def test_no_optimization_result_response(self) -> None:
        assert not hasattr(scoring, "OptimizationResultResponse")


# ===================================================================
# Callback events as CamelModels
# ===================================================================


class TestCallbackEventModels:
    """Callback event dataclasses should be replaced with CamelModels."""

    def test_started_event_serializes(self) -> None:
        event = OptimizationStartedEvent(
            optimization_id="opt_1",
            search_name="GenesByRNASeq",
            record_type="transcript",
            budget=30,
            objective="f1",
            positive_controls_count=10,
            negative_controls_count=5,
            parameter_space=[{"name": "fc", "type": "numeric"}],
        )
        j = event.model_dump(by_alias=True, mode="json")
        assert j["optimizationId"] == "opt_1"
        assert j["searchName"] == "GenesByRNASeq"
        assert j["type"] == "optimization_started"

    def test_trial_progress_event_serializes(self) -> None:
        trial = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.8,
            false_positive_rate=0.1,
            estimated_size=100,
        )
        event = TrialProgressEvent(
            optimization_id="opt_1",
            trial_num=2,
            budget=30,
            trial=trial,
            best_trial=trial,
            recent_trials=[trial],
        )
        j = event.model_dump(by_alias=True, mode="json")
        assert j["type"] == "trial_progress"
        assert j["optimizationId"] == "opt_1"
        assert j["trialNum"] == 2
        assert isinstance(j["trial"], dict)
        assert isinstance(j["bestTrial"], dict)
        assert isinstance(j["recentTrials"], list)

    def test_completed_event_serializes(self) -> None:
        trial = TrialResult(
            trial_number=1,
            parameters={},
            score=0.9,
            recall=0.95,
            false_positive_rate=0.05,
            estimated_size=100,
        )
        event = OptimizationCompletedEvent(
            optimization_id="opt_done",
            status="completed",
            budget=30,
            all_trials=[trial],
            best_trial=trial,
            pareto_frontier=[trial],
            sensitivity={"fc": 0.8},
            total_time_seconds=12.345,
        )
        j = event.model_dump(by_alias=True, mode="json")
        assert j["type"] == "optimization_completed"
        assert j["optimizationId"] == "opt_done"

    def test_error_event_serializes(self) -> None:
        event = OptimizationErrorEvent(
            optimization_id="opt_err",
            error="WDK is down",
        )
        j = event.model_dump(by_alias=True, mode="json")
        assert j["type"] == "optimization_error"
        assert j["optimizationId"] == "opt_err"
        assert j["error"] == "WDK is down"
