"""Unit tests for the in-memory experiment store."""

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


def _make_experiment(
    exp_id: str = "exp_001",
    site_id: str = "plasmodb",
    created_at: str = "2024-01-01T00:00:00",
    benchmark_id: str | None = None,
    is_primary: bool = False,
    user_id: str | None = None,
) -> Experiment:
    return Experiment(
        id=exp_id,
        config=_make_config(site_id),
        created_at=created_at,
        benchmark_id=benchmark_id,
        is_primary_benchmark=is_primary,
        user_id=user_id,
    )


class TestSyncCrud:
    def test_save_and_get(self) -> None:
        store = ExperimentStore()
        exp = _make_experiment()
        store.save(exp)
        assert store.get("exp_001") is exp

    def test_get_missing_returns_none(self) -> None:
        store = ExperimentStore()
        assert store.get("nonexistent") is None

    def test_save_overwrites(self) -> None:
        store = ExperimentStore()
        exp1 = _make_experiment(created_at="2024-01-01T00:00:00")
        exp2 = _make_experiment(created_at="2024-06-01T00:00:00")
        store.save(exp1)
        store.save(exp2)
        assert store.get("exp_001") is exp2

    def test_delete_existing(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment())
        assert store.delete("exp_001") is True
        assert store.get("exp_001") is None

    def test_delete_nonexistent(self) -> None:
        store = ExperimentStore()
        assert store.delete("nonexistent") is False


class TestAsyncGet:
    async def test_returns_from_cache(self) -> None:
        store = ExperimentStore()
        exp = _make_experiment()
        store.save(exp)
        result = await store.aget("exp_001")
        assert result is exp

    async def test_falls_back_to_db_on_cache_miss(self) -> None:
        store = ExperimentStore()
        db_exp = _make_experiment("db-only")

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=db_exp):
            result = await store.aget("db-only")

        assert result is db_exp
        assert store.get("db-only") is db_exp

    async def test_returns_none_when_not_in_cache_or_db(self) -> None:
        store = ExperimentStore()

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=None):
            result = await store.aget("ghost")

        assert result is None


class TestAsyncDelete:
    async def test_removes_from_cache_and_calls_db(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("doomed"))

        with patch.object(store, "_delete_from_db", new_callable=AsyncMock) as mock_del:
            result = await store.adelete("doomed")

        assert result is True
        assert store.get("doomed") is None
        mock_del.assert_awaited_once_with("doomed")


class TestAlistAll:
    async def test_merges_db_and_cache(self) -> None:
        store = ExperimentStore()
        cached = _make_experiment("cached", site_id="plasmo")
        store.save(cached)

        db_only = _make_experiment("db-only", site_id="plasmo")

        with patch(
            "veupath_chatbot.services.experiment.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[db_only],
        ):
            result = await store.alist_all(site_id="plasmo")

        ids = {e.id for e in result}
        assert "cached" in ids
        assert "db-only" in ids

    async def test_cache_overrides_db(self) -> None:
        store = ExperimentStore()
        cached = _make_experiment("same-id", created_at="2025-01-01T00:00:00")
        store.save(cached)

        db_version = _make_experiment("same-id", created_at="2024-01-01T00:00:00")

        with patch(
            "veupath_chatbot.services.experiment.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[db_version],
        ):
            result = await store.alist_all()

        assert len(result) == 1
        assert result[0].created_at == "2025-01-01T00:00:00"

    async def test_filters_by_site_in_cache(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("plasmo-cached", site_id="plasmodb"))
        store.save(_make_experiment("toxo-cached", site_id="toxodb"))

        with patch(
            "veupath_chatbot.services.experiment.store._list_from_db",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await store.alist_all(site_id="plasmodb")

        assert len(result) == 1
        assert result[0].id == "plasmo-cached"


class TestAlistByBenchmark:
    async def test_merges_db_and_cache(self) -> None:
        store = ExperimentStore()
        cached = _make_experiment("cached", benchmark_id="b1", is_primary=True)
        store.save(cached)

        db_only = _make_experiment("db-only", benchmark_id="b1")

        with patch(
            "veupath_chatbot.services.experiment.store._list_by_benchmark_from_db",
            new_callable=AsyncMock,
            return_value=[db_only],
        ):
            result = await store.alist_by_benchmark("b1")

        assert len(result) == 2
        assert result[0].is_primary_benchmark is True

    async def test_cache_overrides_db(self) -> None:
        store = ExperimentStore()
        cached = _make_experiment("same", benchmark_id="b1", created_at="2025-06-01")
        store.save(cached)

        db_version = _make_experiment(
            "same", benchmark_id="b1", created_at="2024-01-01"
        )

        with patch(
            "veupath_chatbot.services.experiment.store._list_by_benchmark_from_db",
            new_callable=AsyncMock,
            return_value=[db_version],
        ):
            result = await store.alist_by_benchmark("b1")

        assert len(result) == 1
        assert result[0].created_at == "2025-06-01"
