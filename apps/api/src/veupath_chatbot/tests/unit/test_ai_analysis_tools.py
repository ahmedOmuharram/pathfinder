"""Tests for ExperimentStore.aget async lookup."""

from unittest.mock import AsyncMock, patch

from veupath_chatbot.services.experiment.store import ExperimentStore
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
)


def _make_experiment(exp_id: str = "exp-1") -> Experiment:
    return Experiment(
        id=exp_id,
        config=ExperimentConfig(
            site_id="plasmodb",
            record_type="gene",
            search_name="GenesByTextSearch",
            parameters={},
            positive_controls=["g1"],
            negative_controls=["n1"],
            controls_search_name="GeneByLocusTag",
            controls_param_name="single_gene_id",
        ),
        wdk_step_id=42,
    )


class TestGetExperiment:
    async def test_aget_finds_db_only_experiment(self) -> None:
        """_get_experiment should use aget() to find experiments
        persisted to DB but not in cache (e.g. after API restart)."""
        store = ExperimentStore()
        db_exp = _make_experiment("db-only")

        assert store.get("db-only") is None

        with patch.object(store, "_load", new_callable=AsyncMock, return_value=db_exp):
            result = await store.aget("db-only")

        assert result is db_exp
        assert store.get("db-only") is db_exp

    async def test_aget_returns_cache_first(self) -> None:
        """When experiment is in cache, aget returns it without DB call."""
        store = ExperimentStore()
        cached = _make_experiment("cached")
        store.save(cached)

        result = await store.aget("cached")
        assert result is cached
