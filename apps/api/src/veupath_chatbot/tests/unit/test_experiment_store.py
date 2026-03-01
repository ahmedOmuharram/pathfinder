"""Unit tests for the in-memory experiment store."""

from __future__ import annotations

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
) -> Experiment:
    return Experiment(
        id=exp_id,
        config=_make_config(site_id),
        created_at=created_at,
        benchmark_id=benchmark_id,
        is_primary_benchmark=is_primary,
    )


class TestExperimentStore:
    def test_save_and_get(self) -> None:
        store = ExperimentStore()
        exp = _make_experiment()
        store.save(exp)
        assert store.get("exp_001") is exp

    def test_get_missing_returns_none(self) -> None:
        store = ExperimentStore()
        assert store.get("nonexistent") is None

    def test_list_all(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("exp_001", created_at="2024-01-01T00:00:00"))
        store.save(_make_experiment("exp_002", created_at="2024-01-02T00:00:00"))
        store.save(_make_experiment("exp_003", created_at="2024-01-03T00:00:00"))

        all_exps = store.list_all()
        assert len(all_exps) == 3
        # Should be sorted newest first
        assert all_exps[0].id == "exp_003"
        assert all_exps[2].id == "exp_001"

    def test_list_all_with_site_filter(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("exp_001", site_id="plasmodb"))
        store.save(_make_experiment("exp_002", site_id="toxodb"))
        store.save(_make_experiment("exp_003", site_id="plasmodb"))

        plasmo = store.list_all(site_id="plasmodb")
        assert len(plasmo) == 2
        assert all(e.config.site_id == "plasmodb" for e in plasmo)

    def test_list_all_empty_site_returns_empty(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("exp_001", site_id="plasmodb"))
        assert store.list_all(site_id="nonexistent") == []

    def test_delete_existing(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment())
        assert store.delete("exp_001") is True
        assert store.get("exp_001") is None

    def test_delete_nonexistent(self) -> None:
        store = ExperimentStore()
        assert store.delete("nonexistent") is False

    def test_save_overwrites(self) -> None:
        store = ExperimentStore()
        exp1 = _make_experiment(created_at="2024-01-01T00:00:00")
        exp2 = _make_experiment(created_at="2024-06-01T00:00:00")
        store.save(exp1)
        store.save(exp2)
        assert store.get("exp_001") is exp2

    def test_list_by_benchmark(self) -> None:
        store = ExperimentStore()
        store.save(_make_experiment("exp_001", benchmark_id="bench_1", is_primary=True))
        store.save(_make_experiment("exp_002", benchmark_id="bench_1"))
        store.save(_make_experiment("exp_003", benchmark_id="bench_2"))

        suite = store.list_by_benchmark("bench_1")
        assert len(suite) == 2
        # Primary should be first
        assert suite[0].is_primary_benchmark is True

    def test_list_by_benchmark_empty(self) -> None:
        store = ExperimentStore()
        assert store.list_by_benchmark("nonexistent") == []
