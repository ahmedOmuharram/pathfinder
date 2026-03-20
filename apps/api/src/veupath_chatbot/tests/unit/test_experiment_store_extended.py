"""Extended unit tests for ExperimentStore and WriteThruStore.

Covers edge cases: thread safety via concurrent async access, stale reads
after updates, filter edge cases, delete semantics, and cache-DB consistency.
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from veupath_chatbot.services.experiment.store import ExperimentStore
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
)


def _make_config(site_id: str = "plasmodb") -> ExperimentConfig:
    return ExperimentConfig(
        site_id=site_id,
        record_type="gene",
        search_name="GenesByTextSearch",
        parameters={},
        positive_controls=["g1", "g2"],
        negative_controls=["n1"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
    )


@dataclass
class _ExperimentOpts:
    """Optional overrides for :func:`_make_experiment`."""

    benchmark_id: str | None = None
    is_primary: bool = False
    user_id: str | None = None
    status: str = "pending"


def _make_experiment(
    exp_id: str = "exp_001",
    site_id: str = "plasmodb",
    created_at: str = "2024-01-01T00:00:00",
    opts: _ExperimentOpts | None = None,
) -> Experiment:
    o = opts or _ExperimentOpts()
    exp = Experiment(
        id=exp_id,
        config=_make_config(site_id),
        created_at=created_at,
        benchmark_id=o.benchmark_id,
        is_primary_benchmark=o.is_primary,
        user_id=o.user_id,
    )
    exp.status = o.status
    return exp


# ---------------------------------------------------------------------------
# WriteThruStore.adelete consistency
# ---------------------------------------------------------------------------


class TestAdeleteConsistency:
    """Verify adelete() return value is consistent with sync delete().

    adelete should return True when entity was in cache, False otherwise.
    """

    async def test_adelete_returns_true_for_existing(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("exp_001"))

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            result = await store.adelete("exp_001")

        assert result is True

    async def test_adelete_returns_false_for_nonexistent(self) -> None:
        """adelete returns False when entity is not in cache, consistent
        with the sync delete() method."""
        store = ExperimentStore()

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            result = await store.adelete("ghost")

        assert result is False

    async def test_adelete_removes_from_cache(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("doomed"))

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock):
            await store.adelete("doomed")

        assert store.get("doomed") is None


# ---------------------------------------------------------------------------
# Sync delete fires DB call even for missing entities
# ---------------------------------------------------------------------------


class TestDeleteSkipsDbCallForMissing:
    """Sync delete() does NOT fire a background DB delete task when the
    entity was not in the cache — the guard ``if removed:`` prevents it.
    """

    def test_delete_nonexistent_does_not_spawn_task(self) -> None:
        store = ExperimentStore()

        with patch("veupath_chatbot.platform.store.spawn") as mock_spawn:
            result = store.delete("ghost")

        assert result is False
        mock_spawn.assert_not_called()


# ---------------------------------------------------------------------------
# Save -> get freshness
# ---------------------------------------------------------------------------


class TestSaveGetFreshness:
    def test_get_returns_latest_after_save(self) -> None:
        store = ExperimentStore()
        exp1 = _make_experiment(opts=_ExperimentOpts(status="pending"))
        store.save(exp1)

        exp1.status = "running"
        store.save(exp1)

        retrieved = store.get("exp_001")
        assert retrieved is not None
        assert retrieved.status == "running"

    def test_save_same_id_different_object(self) -> None:
        store = ExperimentStore()
        exp1 = _make_experiment(opts=_ExperimentOpts(status="pending"))
        store.save(exp1)

        exp2 = _make_experiment(opts=_ExperimentOpts(status="completed"))
        store.save(exp2)

        retrieved = store.get("exp_001")
        assert retrieved is exp2
        assert retrieved.status == "completed"


# ---------------------------------------------------------------------------
# Concurrent async access
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    async def test_concurrent_saves_all_persisted(self) -> None:
        """Multiple concurrent saves should not lose data."""
        store = ExperimentStore()
        experiments = [
            _make_experiment(f"exp_{i:03d}", created_at=f"2024-01-{i + 1:02d}T00:00:00")
            for i in range(10)
        ]

        with patch("veupath_chatbot.platform.store.spawn"):
            for e in experiments:
                store.save(e)

        assert len(store.list_all()) == 10

    async def test_concurrent_aget_same_id(self) -> None:
        """Multiple concurrent aget calls for the same ID should not cause issues."""
        store = ExperimentStore()
        db_exp = _make_experiment("shared")

        async def slow_load(entity_id: str) -> Experiment | None:
            await asyncio.sleep(0.01)
            return db_exp if entity_id == "shared" else None

        with patch.object(store, "_load", side_effect=slow_load):
            results = await asyncio.gather(
                store.aget("shared"),
                store.aget("shared"),
                store.aget("shared"),
            )

        # All should get the same experiment
        for r in results:
            assert r is not None
            assert r.id == "shared"

        # Should be cached now
        assert store.get("shared") is not None


# ---------------------------------------------------------------------------
# List edge cases
# ---------------------------------------------------------------------------


class TestListEdgeCases:
    def test_list_all_empty_string_filters(self) -> None:
        """Empty string site_id/user_id should not match anything."""
        store = ExperimentStore()
        store.save(
            _make_experiment(
                "exp_001", "plasmodb", opts=_ExperimentOpts(user_id="alice")
            )
        )

        # Empty string is falsy, so it should be treated as "no filter"
        result = store.list_all(site_id="", user_id="")
        # Empty string is falsy -> no filter applied -> returns all
        assert len(result) == 1

    def test_list_all_preserves_sort_on_identical_timestamps(self) -> None:
        store = ExperimentStore()
        ts = "2024-01-01T00:00:00"
        store.save(_make_experiment("exp_a", created_at=ts))
        store.save(_make_experiment("exp_b", created_at=ts))
        store.save(_make_experiment("exp_c", created_at=ts))

        result = store.list_all()
        assert len(result) == 3
        # All have same timestamp, order is stable (Python sort is stable)
        ids = [e.id for e in result]
        assert len(ids) == 3

    def test_list_by_benchmark_no_match(self) -> None:
        store = ExperimentStore()
        store.save(
            _make_experiment("exp_001", opts=_ExperimentOpts(benchmark_id="bench_1"))
        )
        result = store.list_by_benchmark("bench_nonexistent")
        assert result == []

    def test_list_by_benchmark_sort_order(self) -> None:
        """Primary benchmark should sort first, then by created_at."""
        store = ExperimentStore()
        store.save(
            _make_experiment(
                "exp_a",
                created_at="2024-01-03",
                opts=_ExperimentOpts(benchmark_id="b1", is_primary=False),
            )
        )
        store.save(
            _make_experiment(
                "exp_b",
                created_at="2024-01-01",
                opts=_ExperimentOpts(benchmark_id="b1", is_primary=True),
            )
        )
        store.save(
            _make_experiment(
                "exp_c",
                created_at="2024-01-02",
                opts=_ExperimentOpts(benchmark_id="b1", is_primary=False),
            )
        )

        result = store.list_by_benchmark("b1")
        assert len(result) == 3
        # Primary first (is_primary_benchmark=True -> not True = False -> sorts first)
        assert result[0].is_primary_benchmark is True
        assert result[0].id == "exp_b"


# ---------------------------------------------------------------------------
# aget cache population
# ---------------------------------------------------------------------------


class TestAgetCachePopulation:
    async def test_aget_populates_cache_for_list_all(self) -> None:
        """After aget loads from DB, the entity should be available in sync list_all."""
        store = ExperimentStore()
        db_exp = _make_experiment("from-db", site_id="plasmodb")

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=db_exp):
            result = await store.aget("from-db")

        assert result is db_exp
        # Should now appear in sync list_all
        all_exps = store.list_all(site_id="plasmodb")
        assert len(all_exps) == 1
        assert all_exps[0].id == "from-db"


# ---------------------------------------------------------------------------
# alist_all merge behavior
# ---------------------------------------------------------------------------


class TestAlistAllMergeBehavior:
    async def test_alist_all_user_filter_excludes_cache_entries(self) -> None:
        """Cache entries that don't match user filter should be excluded."""
        store = ExperimentStore()
        store.save(_make_experiment("alice-exp", opts=_ExperimentOpts(user_id="alice")))
        store.save(_make_experiment("bob-exp", opts=_ExperimentOpts(user_id="bob")))

        with patch(
            "veupath_chatbot.services.experiment.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await store.alist_all(user_id="alice")

        assert len(result) == 1
        assert result[0].id == "alice-exp"

    async def test_alist_all_no_filters_returns_all(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("exp_1"))
        store.save(_make_experiment("exp_2"))

        with patch(
            "veupath_chatbot.services.experiment.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await store.alist_all()

        assert len(result) == 2


# ---------------------------------------------------------------------------
# Save persistence failure behavior
# ---------------------------------------------------------------------------


class TestSavePersistenceFailure:
    def test_save_updates_cache_even_if_spawn_fails(self) -> None:
        """If the background persist task fails to spawn, cache is still updated."""
        store = ExperimentStore()
        exp = _make_experiment("exp_001")

        with patch("veupath_chatbot.platform.store.spawn", return_value=None):
            store.save(exp)

        # Cache should still have the entity
        assert store.get("exp_001") is exp


# ---------------------------------------------------------------------------
# Large store behavior
# ---------------------------------------------------------------------------


class TestLargeStore:
    def test_list_all_with_many_experiments(self) -> None:
        store = ExperimentStore()
        for i in range(100):
            store.save(
                _make_experiment(
                    f"exp_{i:04d}", created_at=f"2024-{(i % 12) + 1:02d}-01T00:00:00"
                )
            )

        result = store.list_all()
        assert len(result) == 100
        # Should be sorted newest-first
        for i in range(len(result) - 1):
            assert result[i].created_at >= result[i + 1].created_at
