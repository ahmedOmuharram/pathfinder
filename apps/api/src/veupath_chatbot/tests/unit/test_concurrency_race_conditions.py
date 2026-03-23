"""Unit tests for concurrency and race-condition safety across the codebase.

Tests five concurrency scenarios using asyncio primitives and unittest.mock
to control scheduling — no DB, no real WDK, no external I/O.

Scenarios:
1. Experiment lock prevents concurrent execution
2. Auto-push lock prevents concurrent pushes
3. Param optimization cache dedup
4. Gene set concurrent deletion
5. Experiment lock with error handling
"""

import asyncio
import contextlib
import time
from collections.abc import Iterator
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import optuna
import pytest

from veupath_chatbot.platform.store import WriteThruStore
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.service import (
    _EXPERIMENT_LOCKS_MAX,
    _experiment_locks,
    _get_experiment_lock,
)
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    ParameterSpec,
)
from veupath_chatbot.services.parameter_optimization.trials import (
    _cache_key,
    _EvalCache,
    _evaluate_trial,
    _KeyLocks,
    _TrialContext,
)
from veupath_chatbot.services.strategies.auto_push import (
    _PUSH_LOCKS_MAX,
    _get_push_lock,
    _push_locks,
    try_auto_push_to_wdk,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_experiment_locks() -> Iterator[None]:
    """Isolate the module-level experiment lock dict between tests."""
    _experiment_locks.clear()
    yield
    _experiment_locks.clear()


@pytest.fixture(autouse=True)
def _clear_push_locks() -> Iterator[None]:
    """Isolate the module-level push lock dict between tests."""
    _push_locks.clear()
    yield
    _push_locks.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trial_context(
    *,
    site_id: str = "plasmodb.org",
    record_type: str = "transcript",
    search_name: str = "GenesByTaxon",
) -> _TrialContext:
    """Build a minimal _TrialContext suitable for cache-dedup tests."""
    study = optuna.create_study(direction="maximize")
    return _TrialContext(
        site_id=site_id,
        record_type=record_type,
        search_name=search_name,
        fixed_parameters={},
        parameter_space=[
            ParameterSpec(name="p", param_type="numeric", min_value=0.0, max_value=1.0),
        ],
        controls_search_name="GenesByTaxon",
        controls_param_name="organism",
        positive_controls=["gene_a", "gene_b"],
        negative_controls=["gene_x"],
        controls_value_format="newline",
        controls_extra_parameters=None,
        id_field=None,
        cfg=OptimizationConfig(budget=10),
        optimization_id="opt_test",
        budget=10,
        study=study,
        progress_callback=None,
        check_cancelled=None,
        start_time=time.monotonic(),
        trials=[],
        best_trial=None,
    )


# ===================================================================
# Test 1: Experiment lock prevents concurrent execution
# ===================================================================


class TestExperimentLockSerialisation:
    """Verify that _get_experiment_lock serialises same-experiment work."""

    async def test_lock_serialises_same_experiment(self) -> None:
        """Two tasks acquiring the same experiment lock must NOT overlap."""
        log: list[str] = []
        lock = _get_experiment_lock("exp_1")

        async def task(name: str) -> None:
            async with lock:
                log.append(f"{name}_start")
                # Yield control so the other task has a chance to interleave
                await asyncio.sleep(0.01)
                log.append(f"{name}_end")

        await asyncio.gather(task("A"), task("B"))

        # The lock serialises: one task must fully complete before the other starts.
        assert log[0].endswith("_start")
        assert log[1].endswith("_end")
        assert log[2].endswith("_start")
        assert log[3].endswith("_end")
        # The first two entries belong to the same task
        first_task = log[0].split("_")[0]
        assert log[1] == f"{first_task}_end"
        second_task = log[2].split("_")[0]
        assert log[3] == f"{second_task}_end"
        # And they are different tasks
        assert first_task != second_task

    async def test_lock_allows_different_experiments(self) -> None:
        """Locks for different experiment IDs must allow overlapping work."""
        log: list[str] = []

        async def task(exp_id: str, name: str) -> None:
            lock = _get_experiment_lock(exp_id)
            async with lock:
                log.append(f"{name}_start")
                await asyncio.sleep(0.02)
                log.append(f"{name}_end")

        await asyncio.gather(task("exp_1", "A"), task("exp_2", "B"))

        # Both tasks should start before either finishes (overlap).
        start_indices = [i for i, e in enumerate(log) if e.endswith("_start")]
        end_indices = [i for i, e in enumerate(log) if e.endswith("_end")]
        # Both starts should happen before any end
        assert max(start_indices) < min(end_indices)

    async def test_lock_eviction_does_not_evict_held_lock(self) -> None:
        """Filling the lock cache to capacity must not evict a held lock."""
        held_id = "exp_held"
        held_lock = _get_experiment_lock(held_id)
        await held_lock.acquire()

        # Fill remaining capacity
        for i in range(_EXPERIMENT_LOCKS_MAX - 1):
            _get_experiment_lock(f"exp_filler_{i}")

        assert len(_experiment_locks) == _EXPERIMENT_LOCKS_MAX

        # Trigger eviction by requesting one more
        _get_experiment_lock("exp_new")

        assert held_id in _experiment_locks, (
            "Held lock was evicted — serialisation guarantee broken"
        )
        assert "exp_new" in _experiment_locks
        held_lock.release()


# ===================================================================
# Test 2: Auto-push lock prevents concurrent pushes
# ===================================================================


class TestAutoPushLock:
    """Verify that try_auto_push_to_wdk skips when a push is in-flight."""

    async def test_concurrent_pushes_only_one_executes(self) -> None:
        """Holding the push lock must cause try_auto_push_to_wdk to skip."""
        strategy_id = uuid4()
        lock = _get_push_lock(strategy_id)

        # Acquire the lock to simulate an in-flight push
        await lock.acquire()
        assert lock.locked()

        # Patch _do_push and async_session_factory so the real code never runs
        with (
            patch(
                "veupath_chatbot.services.strategies.auto_push._do_push",
                new_callable=AsyncMock,
            ) as mock_do_push,
            patch(
                "veupath_chatbot.services.strategies.auto_push.async_session_factory",
            ),
        ):
            await try_auto_push_to_wdk(strategy_id)

            # _do_push should NOT have been called because the lock was held
            mock_do_push.assert_not_called()

        lock.release()

    async def test_different_strategies_push_concurrently(self) -> None:
        """Two different strategy IDs must be able to push simultaneously."""
        call_log: list[str] = []

        async def fake_do_push(_session: object, sid: UUID) -> None:
            call_log.append(f"{sid}_start")
            await asyncio.sleep(0.01)
            call_log.append(f"{sid}_end")

        sid_a = uuid4()
        sid_b = uuid4()

        # Build a mock async context manager for the session factory
        mock_session = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "veupath_chatbot.services.strategies.auto_push._do_push",
                side_effect=fake_do_push,
            ),
            patch(
                "veupath_chatbot.services.strategies.auto_push.async_session_factory",
                return_value=mock_cm,
            ),
        ):
            await asyncio.gather(
                try_auto_push_to_wdk(sid_a),
                try_auto_push_to_wdk(sid_b),
            )

        # Both pushes should have executed (both _start entries present)
        starts = [e for e in call_log if e.endswith("_start")]
        assert len(starts) == 2

    async def test_lock_eviction_preserves_held_locks(self) -> None:
        """Eviction must not remove a locked entry from the push lock cache."""
        held_id = uuid4()
        held_lock = _get_push_lock(held_id)
        await held_lock.acquire()

        # Fill remaining capacity
        for _ in range(_PUSH_LOCKS_MAX - 1):
            _get_push_lock(uuid4())

        assert len(_push_locks) == _PUSH_LOCKS_MAX

        # Trigger eviction
        new_id = uuid4()
        _get_push_lock(new_id)

        assert held_id in _push_locks, "Held push lock was evicted"
        assert new_id in _push_locks
        held_lock.release()


# ===================================================================
# Test 3: Param optimization cache dedup
# ===================================================================


class TestParamOptimizationCacheDedup:
    """Verify that _evaluate_trial deduplicates WDK calls via per-key locking."""

    async def test_cache_prevents_duplicate_wdk_calls(self) -> None:
        """Four concurrent trials with identical params must call WDK exactly once."""
        ctx = _make_trial_context()
        sem = asyncio.Semaphore(4)
        cache: _EvalCache = {}
        key_locks: _KeyLocks = {}

        fake_wdk_result = {
            "target": {"estimatedSize": 100},
            "positive": {"recall": 0.8, "intersectionCount": 40},
            "negative": {"falsePositiveRate": 0.1, "intersectionCount": 5},
        }

        with patch(
            "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
            new_callable=AsyncMock,
            return_value=fake_wdk_result,
        ) as mock_controls:
            # All 4 tasks use the same optimised params
            optimised_params: dict[str, JSONValue] = {"p": 0.5}
            trial_params: JSONObject = {"p": "0.5"}

            results = await asyncio.gather(
                *(
                    _evaluate_trial(
                        ctx, trial_params, optimised_params, sem, cache, key_locks
                    )
                    for _ in range(4)
                )
            )

        # WDK should have been called exactly ONCE
        assert mock_controls.call_count == 1, (
            f"Expected 1 WDK call, got {mock_controls.call_count}"
        )
        # All results should be identical
        for result in results:
            assert result == (fake_wdk_result, "")

    async def test_cache_allows_different_params(self) -> None:
        """Trials with different params must each make their own WDK call."""
        ctx = _make_trial_context()
        sem = asyncio.Semaphore(4)
        cache: _EvalCache = {}
        key_locks: _KeyLocks = {}

        call_count = 0

        async def counting_controls(*_args: object, **_kwargs: object) -> JSONObject:
            nonlocal call_count
            call_count += 1
            return {
                "target": {"estimatedSize": 50},
                "positive": {"recall": 0.5, "intersectionCount": 20},
                "negative": {"falsePositiveRate": 0.05, "intersectionCount": 2},
            }

        with patch(
            "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
            side_effect=counting_controls,
        ):
            param_sets: list[tuple[JSONObject, dict[str, JSONValue]]] = [
                ({"p": str(round(i * 0.1, 5))}, {"p": round(i * 0.1, 5)})
                for i in range(4)
            ]

            await asyncio.gather(
                *(
                    _evaluate_trial(ctx, tp, op, sem, cache, key_locks)
                    for tp, op in param_sets
                )
            )

        # Each distinct param set triggers its own WDK call
        assert call_count == 4, f"Expected 4 WDK calls, got {call_count}"

    async def test_cache_hit_returns_immediately(self) -> None:
        """Pre-populated cache must be returned without any WDK call."""
        ctx = _make_trial_context()
        sem = asyncio.Semaphore(4)
        key_locks: _KeyLocks = {}

        optimised_params: dict[str, JSONValue] = {"p": 0.42}
        key = _cache_key(optimised_params)
        cached_value: JSONObject = {"target": {"estimatedSize": 77}}
        cached_result: tuple[JSONObject | None, str] = (cached_value, "")
        cache: _EvalCache = {key: cached_result}

        with patch(
            "veupath_chatbot.services.parameter_optimization.trials.run_positive_negative_controls",
            new_callable=AsyncMock,
        ) as mock_controls:
            tp: JSONObject = {"p": "0.42"}
            result = await _evaluate_trial(
                ctx, tp, optimised_params, sem, cache, key_locks
            )

        mock_controls.assert_not_called()
        assert result == cached_result


# ===================================================================
# Test 4: Gene set concurrent deletion
# ===================================================================


@dataclass
class _FakeEntity:
    """Minimal entity satisfying the Identifiable protocol."""

    id: str


class _FakeModel:
    """Minimal stand-in for an ORM model (needed by WriteThruStore)."""

    __tablename__ = "fake"
    id = "id"


class _TestStore(WriteThruStore["_FakeEntity"]):
    """Concrete WriteThruStore for testing (no real DB)."""

    _model = _FakeModel
    _to_row = staticmethod(lambda e: {"id": e.id})
    _from_row = staticmethod(lambda r: _FakeEntity(id=r.id))


class TestGeneSetConcurrentDeletion:
    """Verify that WriteThruStore.delete() handles concurrent deletions safely."""

    def test_double_delete_second_returns_false(self) -> None:
        """First delete returns True, second returns False."""
        store: _TestStore = _TestStore()
        entity = _FakeEntity(id="ent_1")
        store._cache[entity.id] = entity

        # Patch spawn so fire-and-forget DB delete doesn't run
        with patch("veupath_chatbot.platform.store.spawn"):
            first = store.delete("ent_1")
            second = store.delete("ent_1")

        assert first is True
        assert second is False

    async def test_concurrent_delete_only_one_succeeds(self) -> None:
        """Two simultaneous adelete() calls on the same entity: only one returns True."""
        store: _TestStore = _TestStore()
        entity = _FakeEntity(id="ent_2")
        store._cache[entity.id] = entity

        # Patch _delete_from_db to avoid real DB calls
        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            results = await asyncio.gather(
                store.adelete("ent_2"),
                store.adelete("ent_2"),
            )

        # Exactly one True and one False (the entity is removed once)
        assert sorted(results) == [False, True]


# ===================================================================
# Test 5: Experiment lock with error handling
# ===================================================================


class TestExperimentLockErrorHandling:
    """Verify that the experiment lock is released even when exceptions occur."""

    async def test_lock_released_on_exception(self) -> None:
        """An exception during an experiment run must still release the lock."""
        lock = _get_experiment_lock("exp_err")

        async with lock:
            # Simulate work followed by a caught exception inside the lock
            with contextlib.suppress(RuntimeError):
                _raise_runtime_error()

        # Lock must NOT be held after the context manager exits
        assert not lock.locked(), (
            "Lock was not released after exception inside async-with block"
        )

    async def test_lock_released_after_unhandled_exception(self) -> None:
        """Even with an unhandled error, the lock must be freed for reuse."""
        lock = _get_experiment_lock("exp_unhandled")

        with pytest.raises(ValueError, match="boom"):
            async with lock:
                _raise_value_error()

        # The lock should be released despite the exception propagating
        assert not lock.locked()

    async def test_subsequent_task_can_acquire_after_failure(self) -> None:
        """After a failed task releases the lock, the next task can acquire it."""
        exp_id = "exp_retry"
        lock = _get_experiment_lock(exp_id)
        log: list[str] = []

        async def failing_task() -> None:
            async with lock:
                log.append("fail_start")
                _raise_runtime_error()

        async def succeeding_task() -> None:
            async with lock:
                log.append("success_start")
                log.append("success_end")

        # First task fails
        with pytest.raises(RuntimeError, match="crash"):
            await failing_task()

        assert not lock.locked(), "Lock not released after failing task"

        # Second task should acquire without deadlock
        await succeeding_task()
        assert "success_start" in log
        assert "success_end" in log


# ---------------------------------------------------------------------------
# Exception helpers (satisfy EM101 / TRY301)
# ---------------------------------------------------------------------------


def _raise_runtime_error() -> None:
    msg = "crash"
    raise RuntimeError(msg)


def _raise_value_error() -> None:
    msg = "boom"
    raise ValueError(msg)
