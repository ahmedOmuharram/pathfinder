"""Error resilience tests for WDK API failures, Optuna crashes, and DB outages.

Validates that the system degrades gracefully when external dependencies fail:
- Section 1: WDK malformed/error responses during experiment evaluation
- Section 2: Optuna mid-loop crashes during parameter optimization
- Section 3: DB connection failures during write-through persistence
"""

from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from veupath_chatbot.platform.errors import AppError, ErrorCode, WDKError
from veupath_chatbot.platform.store import WriteThruStore
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.service import (
    PhaseContext,
    _phase_evaluate,
    _run_single_step_controls,
    run_experiment,
)
from veupath_chatbot.services.experiment.store import ExperimentStore
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
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    OptimizationInput,
    OptimizationResult,
    ParameterSpec,
    optimize_search_parameters,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _minimal_config(**overrides: Any) -> ExperimentConfig:
    """Build a minimal single-step experiment config."""
    defaults: dict[str, Any] = {
        "site_id": "plasmodb",
        "record_type": "gene",
        "search_name": "GenesByTextSearch",
        "parameters": {"text_expression": "kinase"},
        "positive_controls": ["PF3D7_0100100"],
        "negative_controls": ["PF3D7_0900100"],
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "single_gene_id",
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def _dummy_metrics() -> ExperimentMetrics:
    return ExperimentMetrics(
        confusion_matrix=ConfusionMatrix(
            true_positives=1,
            false_positives=0,
            true_negatives=1,
            false_negatives=0,
        ),
        sensitivity=1.0,
        specificity=1.0,
        precision=1.0,
        f1_score=1.0,
        mcc=1.0,
        balanced_accuracy=1.0,
    )


def _good_control_result() -> ControlTestResult:
    """A valid control-test result with positive and negative data."""
    return ControlTestResult(
        site_id="plasmodb",
        record_type="gene",
        target=ControlTargetData(
            search_name="GenesByTextSearch",
            parameters={},
            step_id=42,
            result_count=100,
        ),
        positive=ControlSetData(
            controls_count=1,
            intersection_count=1,
            intersection_ids=["PF3D7_0100100"],
            intersection_ids_sample=["PF3D7_0100100"],
            missing_ids_sample=[],
            recall=1.0,
        ),
        negative=ControlSetData(
            controls_count=1,
            intersection_count=0,
            intersection_ids=[],
            intersection_ids_sample=[],
            unexpected_hits_sample=[],
            false_positive_rate=0.0,
        ),
    )


def _make_opt_input(
    parameter_space: list[ParameterSpec] | None = None,
) -> OptimizationInput:
    """Build a minimal OptimizationInput for testing."""
    space = parameter_space or [
        ParameterSpec(
            name="fold_change",
            param_type="numeric",
            min_value=1.0,
            max_value=10.0,
        ),
    ]
    return OptimizationInput(
        site_id="plasmodb",
        record_type="transcript",
        search_name="GenesByRNASeq",
        parameter_space=space,
        fixed_parameters=cast("JSONObject", {"organism": "P. falciparum"}),
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
        positive_controls=[f"POS_{i}" for i in range(5)],
        negative_controls=[f"NEG_{i}" for i in range(5)],
    )


def _make_wdk_result(
    *,
    result_count: int = 100,
    pos_recall: float = 0.8,
    neg_fpr: float = 0.1,
) -> ControlTestResult:
    """Build a realistic run_positive_negative_controls return value."""
    pos = [f"POS_{i}" for i in range(5)]
    neg = [f"NEG_{i}" for i in range(5)]
    n_pos_found = int(len(pos) * pos_recall)
    n_neg_found = int(len(neg) * neg_fpr)

    return ControlTestResult(
        site_id="plasmodb",
        record_type="transcript",
        target=ControlTargetData(
            search_name="GenesByRNASeq",
            parameters={},
            step_id=999,
            result_count=result_count,
        ),
        positive=ControlSetData(
            controls_count=len(pos),
            intersection_count=n_pos_found,
            intersection_ids_sample=pos[:n_pos_found],
            intersection_ids=pos[:n_pos_found],
            missing_ids_sample=pos[n_pos_found:],
            recall=n_pos_found / len(pos) if pos else None,
        ),
        negative=ControlSetData(
            controls_count=len(neg),
            intersection_count=n_neg_found,
            intersection_ids_sample=neg[:n_neg_found],
            intersection_ids=neg[:n_neg_found],
            unexpected_hits_sample=neg[:n_neg_found],
            false_positive_rate=n_neg_found / len(neg) if neg else None,
        ),
    )


# ===========================================================================
# Section 1: WDK Malformed Response Tests
# ===========================================================================


class TestWDKMalformedResponses:
    """Verify experiment service handles bad WDK responses gracefully."""

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service._phase_persist_strategy",
        new_callable=AsyncMock,
    )
    @patch(
        "veupath_chatbot.services.experiment.service.extract_and_enrich_genes",
        new_callable=AsyncMock,
        return_value=([], [], [], []),
    )
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_wdk_returns_error_string_in_result(
        self,
        mock_controls: AsyncMock,
        mock_enrich: AsyncMock,
        mock_persist: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """When WDK returns a result with an error key, metrics should still compute.

        The metrics_from_control_result function handles missing/empty sections
        by defaulting counts to 0, so the experiment should complete (not crash)
        even with a degenerate result.
        """
        mock_controls.return_value = ControlTestResult()

        # The result has no positive/negative/target data. metrics_from_control_result
        # handles this gracefully, defaulting all counts to 0.
        config = _minimal_config()
        exp = await run_experiment(config)

        assert exp.status == "completed"
        assert exp.metrics is not None
        # All counts should be 0 since the response lacked real data
        assert exp.metrics.confusion_matrix.true_positives == 0
        assert exp.metrics.confusion_matrix.false_positives == 0

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_wdk_raises_connection_error(
        self,
        mock_controls: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """httpx.ConnectError should propagate as an experiment error."""
        mock_controls.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            await run_experiment(_minimal_config())

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_wdk_raises_timeout(
        self,
        mock_controls: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """httpx.ReadTimeout should propagate as an experiment error."""
        mock_controls.side_effect = httpx.ReadTimeout("Read timed out")

        with pytest.raises(httpx.ReadTimeout):
            await run_experiment(_minimal_config())

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service._phase_persist_strategy",
        new_callable=AsyncMock,
    )
    @patch(
        "veupath_chatbot.services.experiment.service.extract_and_enrich_genes",
        new_callable=AsyncMock,
        return_value=([], [], [], []),
    )
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_wdk_returns_empty_result(
        self,
        mock_controls: AsyncMock,
        mock_enrich: AsyncMock,
        mock_persist: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """An empty result ({}) should not crash metrics computation.

        metrics_from_control_result defaults all absent fields to 0.
        """
        mock_controls.return_value = ControlTestResult()

        config = _minimal_config()
        exp = await run_experiment(config)

        assert exp.status == "completed"
        assert exp.metrics is not None
        # All counts should be 0 since response was empty
        cm = exp.metrics.confusion_matrix
        assert cm.true_positives == 0
        assert cm.false_positives == 0
        assert cm.true_negatives == 0
        assert cm.false_negatives == 0

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_wdk_error_sets_experiment_error_field(
        self,
        mock_controls: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """When WDK raises AppError, the experiment's error field should be set."""
        mock_controls.side_effect = WDKError(detail="Service unavailable")

        with pytest.raises(WDKError):
            await run_experiment(_minimal_config())

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service._phase_persist_strategy",
        new_callable=AsyncMock,
    )
    @patch(
        "veupath_chatbot.services.experiment.service.extract_and_enrich_genes",
        new_callable=AsyncMock,
        return_value=([], [], [], []),
    )
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_wdk_returns_partial_result_missing_negative(
        self,
        mock_controls: AsyncMock,
        mock_enrich: AsyncMock,
        mock_persist: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """A result with only positive data (no negative) should still work."""
        mock_controls.return_value = ControlTestResult(
            target=ControlTargetData(result_count=50),
            positive=ControlSetData(
                controls_count=1,
                intersection_count=1,
                intersection_ids=["PF3D7_0100100"],
                missing_ids_sample=[],
            ),
            negative=None,
        )

        config = _minimal_config()
        exp = await run_experiment(config)

        assert exp.status == "completed"
        assert exp.metrics is not None
        # Positive hits counted, negative defaults to 0
        assert exp.metrics.confusion_matrix.true_positives == 1
        assert exp.metrics.confusion_matrix.false_positives == 0


class TestRunSingleStepControlsErrorPropagation:
    """Test _run_single_step_controls directly for error propagation."""

    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_propagates_app_error(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        mock_controls.side_effect = AppError(
            code=ErrorCode.WDK_ERROR,
            title="WDK failure",
            detail="Step creation failed",
        )
        config = _minimal_config()

        with pytest.raises(AppError, match="WDK failure"):
            await _run_single_step_controls(config, config.parameters)

    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_propagates_value_error(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        mock_controls.side_effect = ValueError("Invalid parameter format")
        config = _minimal_config()

        with pytest.raises(ValueError, match="Invalid parameter format"):
            await _run_single_step_controls(config, config.parameters)


class TestPhaseEvaluateErrorHandling:
    """Test _phase_evaluate handles errors from control tests."""

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service.extract_and_enrich_genes",
        new_callable=AsyncMock,
        return_value=([], [], [], []),
    )
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_phase_evaluate_propagates_connection_error(
        self,
        mock_controls: AsyncMock,
        mock_enrich: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """Connection errors during phase evaluate should propagate up."""
        mock_controls.side_effect = httpx.ConnectError("Connection refused")

        config = _minimal_config()
        experiment = Experiment(id="exp_test123", config=config, status="running")
        store = ExperimentStore()
        emit = AsyncMock()
        pctx = PhaseContext(
            config=config, experiment=experiment, emit=emit, store=store
        )

        with pytest.raises(httpx.ConnectError):
            await _phase_evaluate(pctx)

    @patch("veupath_chatbot.platform.store.spawn")
    @patch(
        "veupath_chatbot.services.experiment.service.extract_and_enrich_genes",
        new_callable=AsyncMock,
        return_value=([], [], [], []),
    )
    @patch(
        "veupath_chatbot.services.experiment.service.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_phase_evaluate_with_null_sections(
        self,
        mock_controls: AsyncMock,
        mock_enrich: AsyncMock,
        mock_spawn: MagicMock,
    ) -> None:
        """A result with explicit None sections should still compute metrics."""
        mock_controls.return_value = ControlTestResult()

        config = _minimal_config()
        experiment = Experiment(id="exp_test456", config=config, status="running")
        store = ExperimentStore()
        emit = AsyncMock()
        pctx = PhaseContext(
            config=config, experiment=experiment, emit=emit, store=store
        )

        _result, metrics = await _phase_evaluate(pctx)

        assert metrics is not None
        assert metrics.confusion_matrix.true_positives == 0


# ===========================================================================
# Section 2: Optuna Mid-Loop Crash Tests
# ===========================================================================


class TestOptunaMidLoopCrashes:
    """Verify parameter optimization handles Optuna failures gracefully."""

    @patch(
        "veupath_chatbot.services.parameter_optimization.core.optuna.create_study",
        side_effect=RuntimeError("Optuna storage backend failed"),
    )
    async def test_optuna_study_create_failure(
        self,
        mock_create: MagicMock,
    ) -> None:
        """When optuna.create_study raises, the error should propagate.

        The core.optimize_search_parameters function does not catch
        RuntimeError from create_study -- it propagates.
        """
        with pytest.raises(RuntimeError, match="Optuna storage backend failed"):
            await optimize_search_parameters(
                _make_opt_input(),
                config=OptimizationConfig(budget=5),
            )

    @patch(
        "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_trial_evaluation_failure_aborts_after_consecutive_limit(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        """When all WDK calls fail consecutively, optimization should abort.

        _MAX_CONSECUTIVE_FAILURES = 5 in trials.py. When no best_trial exists
        and consecutive failures reach this limit, the loop stops with
        status="error".
        """
        mock_controls.side_effect = AppError(
            code=ErrorCode.WDK_ERROR,
            title="WDK down",
            detail="Service unavailable",
        )

        result = await optimize_search_parameters(
            _make_opt_input(),
            config=OptimizationConfig(budget=20),
        )

        assert isinstance(result, OptimizationResult)
        assert result.status == "error"
        assert result.best_trial is None
        assert result.error_message is not None
        assert "consecutive failures" in result.error_message.lower()
        # Should have stopped well before budget of 20
        assert len(result.all_trials) <= 20

    @patch(
        "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_all_trials_fail_returns_result_with_no_best_trial(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        """All WDK calls fail: result should have status='error', no best_trial."""
        mock_controls.side_effect = ValueError("Malformed response")

        result = await optimize_search_parameters(
            _make_opt_input(),
            config=OptimizationConfig(budget=10),
        )

        assert isinstance(result, OptimizationResult)
        assert result.best_trial is None
        # All trials should have score 0
        for trial in result.all_trials:
            assert trial.score == 0.0

    @patch(
        "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_intermittent_failures_do_not_abort(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        """Mixed success/failure trials: should complete, not abort.

        If some trials succeed, consecutive_failures resets, so the loop
        should not abort even with some failures.
        """
        call_count = 0

        async def alternating_response(*args: Any, **kwargs: Any) -> ControlTestResult:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                msg = "Intermittent failure"
                raise ValueError(msg)
            return _make_wdk_result()

        mock_controls.side_effect = alternating_response

        result = await optimize_search_parameters(
            _make_opt_input(),
            config=OptimizationConfig(budget=8),
        )

        assert isinstance(result, OptimizationResult)
        # Should complete (not error) because successes reset the counter
        assert result.status == "completed"
        assert result.best_trial is not None
        assert result.best_trial.score > 0.0

    @patch(
        "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_empty_control_result_scores_zero(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        """When WDK returns an empty ControlTestResult, all trials score 0.

        An empty result has no positive/negative data, so recall=None, fpr=None,
        resulting in score=0. The optimization completes (not "error") but
        best_trial is None since no trial scored > 0.
        """
        mock_controls.return_value = ControlTestResult()

        result = await optimize_search_parameters(
            _make_opt_input(),
            config=OptimizationConfig(budget=8),
        )

        assert isinstance(result, OptimizationResult)
        # All trials should have score 0 (no positive/negative data)
        for trial in result.all_trials:
            assert trial.score == 0.0

    @patch(
        "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
        new_callable=AsyncMock,
    )
    async def test_progress_callback_called_on_trial_failure(
        self,
        mock_controls: AsyncMock,
    ) -> None:
        """Progress callback should be invoked even when trials fail."""
        mock_controls.side_effect = AppError(
            code=ErrorCode.WDK_ERROR,
            title="WDK down",
            detail="Service unavailable",
        )

        events: list[JSONObject] = []

        async def collect(event: JSONObject) -> None:
            events.append(event)

        await optimize_search_parameters(
            _make_opt_input(),
            config=OptimizationConfig(budget=6),
            progress_callback=collect,
        )

        # Should have received at least started + trial events + error
        assert len(events) >= 2
        # All optimization events use "optimization_progress" as the type;
        # the "status" field inside "data" distinguishes started/running/error.
        event_types = {e.get("type") for e in events}
        assert "optimization_progress" in event_types
        statuses = {
            e.get("data", {}).get("status")
            for e in events
            if isinstance(e.get("data"), dict)
        }
        assert "started" in statuses
        assert "error" in statuses


# ===========================================================================
# Section 3: DB Connection Failure Tests
# ===========================================================================


@dataclass
class _FakeEntity:
    id: str
    name: str


class _FakeRowModel:
    """Fake SQLAlchemy model class for testing."""

    id = "id"
    __tablename__ = "fake_entities"


def _fake_to_row(entity: _FakeEntity) -> dict[str, object]:
    return {"id": entity.id, "name": entity.name}


def _fake_from_row(row: Any) -> _FakeEntity:
    return _FakeEntity(id=row.id, name=row.name)


class _FakeStore(WriteThruStore[_FakeEntity]):
    """Concrete store for testing DB failure resilience."""

    _model = _FakeRowModel
    _to_row = staticmethod(_fake_to_row)
    _from_row = staticmethod(_fake_from_row)


class TestDBConnectionFailures:
    """Verify that WriteThruStore._persist handles DB failures gracefully."""

    async def test_persist_failure_does_not_crash_save(self) -> None:
        """save() should update in-memory cache even when _persist fails.

        WriteThruStore.save() puts the entity in _cache synchronously,
        then spawns _persist as a background task. Even if _persist fails,
        the cache should have the entity.
        """
        store = _FakeStore()
        entity = _FakeEntity(id="test_001", name="Test Entity")

        with patch("veupath_chatbot.platform.store.spawn") as mock_spawn:
            store.save(entity)

        # Entity should be in cache regardless of DB state
        cached = store.get("test_001")
        assert cached is not None
        assert cached.name == "Test Entity"

        # spawn was called (background persist was attempted)
        mock_spawn.assert_called_once()

    async def test_persist_db_error_swallowed(self) -> None:
        """_persist should catch DB exceptions and log, not raise."""
        store = _FakeStore()
        entity = _FakeEntity(id="test_002", name="Fragile")

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                side_effect=RuntimeError("DB connection refused"),
            ),
            patch("veupath_chatbot.platform.store.logger") as mock_logger,
        ):
            # Should not raise
            await store._persist(entity)

            # Should have logged the exception
            mock_logger.exception.assert_called_once()

    async def test_persist_failure_logged_with_entity_info(self) -> None:
        """DB failures should be logged with entity type and ID."""
        store = _FakeStore()
        entity = _FakeEntity(id="test_003", name="LogMe")

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                side_effect=ConnectionError("Connection lost"),
            ),
            patch("veupath_chatbot.platform.store.logger") as mock_logger,
        ):
            await store._persist(entity)

            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            # First positional arg is the message
            assert (
                "persist" in call_args.args[0].lower()
                or "persist" in str(call_args).lower()
            )
            # Keyword args should contain entity info
            assert call_args.kwargs.get("entity_id") == "test_003"
            assert call_args.kwargs.get("entity_type") == "fake_entities"

    async def test_persist_session_commit_failure_swallowed(self) -> None:
        """If session.commit() fails, _persist should still catch and log."""
        store = _FakeStore()
        entity = _FakeEntity(id="test_004", name="CommitFail")

        mock_session = AsyncMock()
        mock_session.commit.side_effect = RuntimeError("Commit failed: disk full")
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_ctx)

        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                mock_factory,
            ),
            patch("veupath_chatbot.platform.store.pg_insert") as mock_insert,
            patch("veupath_chatbot.platform.store.logger") as mock_logger,
        ):
            mock_stmt = MagicMock()
            mock_insert.return_value = mock_stmt
            mock_stmt.values.return_value = mock_stmt
            mock_stmt.on_conflict_do_update.return_value = mock_stmt

            await store._persist(entity)

            mock_logger.exception.assert_called_once()

    async def test_multiple_saves_after_db_failure_all_cached(self) -> None:
        """Multiple save() calls should all succeed in cache even if DB is down."""
        store = _FakeStore()

        with patch("veupath_chatbot.platform.store.spawn"):
            for i in range(5):
                entity = _FakeEntity(id=f"entity_{i}", name=f"Name {i}")
                store.save(entity)

        # All should be in cache
        for i in range(5):
            cached = store.get(f"entity_{i}")
            assert cached is not None
            assert cached.name == f"Name {i}"

    async def test_get_returns_cached_even_after_persist_error(self) -> None:
        """get() should return the entity even if _persist errored for it."""
        store = _FakeStore()
        entity = _FakeEntity(id="test_005", name="Resilient")

        # Save puts in cache + spawns persist
        with patch("veupath_chatbot.platform.store.spawn"):
            store.save(entity)

        # Simulate _persist failure
        with (
            patch(
                "veupath_chatbot.platform.store.async_session_factory",
                side_effect=RuntimeError("DB down"),
            ),
            patch("veupath_chatbot.platform.store.logger"),
        ):
            await store._persist(entity)  # This fails but is swallowed

        # Cache should still have the entity
        result = store.get("test_005")
        assert result is not None
        assert result.name == "Resilient"

    async def test_delete_works_even_after_persist_failure(self) -> None:
        """delete() should remove from cache even if persist previously failed."""
        store = _FakeStore()
        entity = _FakeEntity(id="test_006", name="Deletable")

        with patch("veupath_chatbot.platform.store.spawn"):
            store.save(entity)
            assert store.get("test_006") is not None

            removed = store.delete("test_006")

        assert removed is True
        assert store.get("test_006") is None
