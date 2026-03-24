"""Tests for public strategy text matching."""

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStrategySummary
from veupath_chatbot.services.catalog.public_strategy_search import (
    rank_public_strategies,
)


def _strat(
    name: str, description: str = "", name_of_first_step: str = "", **kw: object
) -> WDKStrategySummary:
    return WDKStrategySummary(
        strategy_id=kw.get("strategy_id", 1),
        name=name,
        root_step_id=1,
        description=description,
        name_of_first_step=name_of_first_step,
        author=kw.get("author", ""),
        record_class_name=kw.get("record_class_name", "gene"),
    )


class TestRankPublicStrategies:
    def test_exact_name_match_ranked_first(self) -> None:
        strategies = [
            _strat("Unrelated strategy", "Something else"),
            _strat("RNA-seq gametocyte genes"),
            _strat("Another one", "gametocyte analysis"),
        ]
        results = rank_public_strategies(
            strategies, query="RNA-seq gametocyte", limit=3
        )
        assert results[0]["name"] == "RNA-seq gametocyte genes"

    def test_description_match_contributes(self) -> None:
        strategies = [
            _strat("Strategy A", "Find kinase genes in P. falciparum"),
            _strat("Strategy B", "Unrelated stuff"),
        ]
        results = rank_public_strategies(strategies, query="kinase falciparum", limit=3)
        assert results[0]["name"] == "Strategy A"

    def test_limit_respected(self) -> None:
        strategies = [_strat(f"Strategy {i}", "gene") for i in range(10)]
        results = rank_public_strategies(strategies, query="gene", limit=3)
        assert len(results) == 3

    def test_zero_score_excluded(self) -> None:
        strategies = [
            _strat("Malaria vaccine candidates", "epitope analysis"),
            _strat("Cooking recipes", "pasta carbonara"),
        ]
        results = rank_public_strategies(strategies, query="malaria epitope", limit=3)
        assert len(results) == 1
        assert results[0]["name"] == "Malaria vaccine candidates"

    def test_empty_query_returns_empty(self) -> None:
        strategies = [_strat("Something")]
        results = rank_public_strategies(strategies, query="", limit=3)
        assert results == []

    def test_case_insensitive(self) -> None:
        strategies = [_strat("RNA-Seq Analysis")]
        results = rank_public_strategies(strategies, query="rna-seq", limit=3)
        assert len(results) == 1

    def test_name_weighted_higher_than_description(self) -> None:
        strategies = [
            _strat("Ortholog mapping", "general analysis"),
            _strat("General analysis", "ortholog mapping results"),
        ]
        results = rank_public_strategies(strategies, query="ortholog mapping", limit=3)
        assert results[0]["name"] == "Ortholog mapping"

    def test_results_are_serialized_dicts(self) -> None:
        strategies = [_strat("Test", strategy_id=42)]
        results = rank_public_strategies(strategies, query="test", limit=3)
        assert len(results) == 1
        assert (
            results[0]["strategyId"] == 42
        )  # camelCase from model_dump(by_alias=True)
