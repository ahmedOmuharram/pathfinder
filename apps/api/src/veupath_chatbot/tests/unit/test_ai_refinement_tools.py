"""Unit tests for AI experiment strategy refinement tools — error paths.

Tests the RefinementToolsMixin error-path methods that require no WDK I/O:
- Missing experiment, strategy, or step_id early-returns.
- WDKError propagation during step creation.
- Gene info metadata loss after re-evaluation (pure domain behavior).

Happy-path tests that previously mocked get_strategy_api have moved to
``tests/integration/test_ai_refinement_tools.py`` with VCR cassettes.
"""

from unittest.mock import AsyncMock, patch

import pytest

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.experiment.ai_refinement_tools import RefinementToolsMixin
from veupath_chatbot.services.experiment.store import ExperimentStore
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    GeneInfo,
)


def _cfg() -> ExperimentConfig:
    return ExperimentConfig(
        site_id="plasmodb",
        record_type="gene",
        search_name="GenesByTextSearch",
        parameters={},
        positive_controls=["g1", "g2", "g3"],
        negative_controls=["n1", "n2"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
    )


def _exp(
    exp_id: str = "exp_001",
    wdk_strategy_id: int | None = 42,
    wdk_step_id: int | None = 99,
) -> Experiment:
    exp = Experiment(id=exp_id, config=_cfg())
    exp.wdk_strategy_id = wdk_strategy_id
    exp.wdk_step_id = wdk_step_id
    exp.true_positive_genes = [GeneInfo(id="g1"), GeneInfo(id="g2")]
    exp.false_negative_genes = [GeneInfo(id="g3")]
    exp.false_positive_genes = [GeneInfo(id="n1")]
    exp.true_negative_genes = [GeneInfo(id="n2")]
    return exp


class ConcreteRefinementAgent(RefinementToolsMixin):
    """Concrete implementation for testing the mixin."""

    def __init__(self, site_id: str, experiment: Experiment | None) -> None:
        self.site_id = site_id
        self._experiment = experiment

    async def _get_experiment(self) -> Experiment | None:
        return self._experiment


# ---------------------------------------------------------------------------
# refine_with_search — error paths
# ---------------------------------------------------------------------------


class TestRefineWithSearchErrors:
    async def test_returns_error_when_no_experiment(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent.refine_with_search(
            search_name="GenesByText",
            parameters={"text": "kinase"},
        )
        assert "error" in result

    async def test_returns_error_when_no_strategy(self) -> None:
        exp = _exp(wdk_strategy_id=None)
        agent = ConcreteRefinementAgent("plasmodb", exp)
        result = await agent.refine_with_search(
            search_name="GenesByText",
            parameters={"text": "kinase"},
        )
        assert "error" in result

    async def test_returns_error_when_no_step_id(self) -> None:
        exp = _exp(wdk_step_id=None)
        agent = ConcreteRefinementAgent("plasmodb", exp)
        result = await agent.refine_with_search(
            search_name="GenesByText",
            parameters={"text": "kinase"},
        )
        assert "error" in result

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    async def test_raises_when_step_creation_fails(
        self, mock_get_api: AsyncMock
    ) -> None:
        api = AsyncMock()
        api.create_step.side_effect = WDKError(detail="bad params")
        mock_get_api.return_value = api

        agent = ConcreteRefinementAgent("plasmodb", _exp())
        with pytest.raises(WDKError, match="bad params"):
            await agent.refine_with_search(
                search_name="GenesByText",
                parameters={"text": "kinase"},
            )


# ---------------------------------------------------------------------------
# refine_with_gene_ids — error paths
# ---------------------------------------------------------------------------


class TestRefineWithGeneIdsErrors:
    async def test_returns_error_when_no_experiment(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent.refine_with_gene_ids(gene_ids=["g1"])
        assert "error" in result


# ---------------------------------------------------------------------------
# re_evaluate_controls — error paths + domain logic
# ---------------------------------------------------------------------------


class TestReEvaluateControlsErrors:
    async def test_returns_error_when_no_experiment(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent.re_evaluate_controls()
        assert "error" in result

    async def test_returns_error_when_no_step_id(self) -> None:
        exp = _exp(wdk_step_id=None)
        agent = ConcreteRefinementAgent("plasmodb", exp)
        result = await agent.re_evaluate_controls()
        assert "error" in result


class TestReEvaluateControlsDomainLogic:
    """Tests that verify the classification logic with controlled result sets.

    These mock only collect_all_result_ids (which does WDK I/O) and test that
    the gene classification (TP/FN/FP/TN) is correct given a known result set.
    """

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.collect_all_result_ids",
        new_callable=AsyncMock,
    )
    async def test_re_evaluate_updates_metrics(
        self,
        mock_collect: AsyncMock,
        mock_get_api: AsyncMock,
    ) -> None:
        """After refinement, re_evaluate_controls should update all gene lists."""
        mock_collect.return_value = {"g1", "g3", "n2"}  # g1 TP, g3 TP, n2 FP
        api = AsyncMock()
        mock_get_api.return_value = api

        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent("plasmodb", exp)

        with patch(
            "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.re_evaluate_controls()

        assert result["success"] is True
        assert result["totalResults"] == 3

        tp_ids = {g.id for g in exp.true_positive_genes}
        fn_ids = {g.id for g in exp.false_negative_genes}
        fp_ids = {g.id for g in exp.false_positive_genes}
        tn_ids = {g.id for g in exp.true_negative_genes}

        assert tp_ids == {"g1", "g3"}
        assert fn_ids == {"g2"}
        assert fp_ids == {"n2"}
        assert tn_ids == {"n1"}

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.collect_all_result_ids",
        new_callable=AsyncMock,
    )
    async def test_re_evaluate_with_empty_results(
        self,
        mock_collect: AsyncMock,
        mock_get_api: AsyncMock,
    ) -> None:
        """When result set is empty, all positives are FN, all negatives are TN."""
        mock_collect.return_value = set()
        api = AsyncMock()
        mock_get_api.return_value = api

        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent("plasmodb", exp)

        with patch(
            "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.re_evaluate_controls()

        assert result["success"] is True
        assert result["totalResults"] == 0
        assert len(exp.true_positive_genes) == 0
        assert len(exp.false_negative_genes) == 3
        assert len(exp.false_positive_genes) == 0
        assert len(exp.true_negative_genes) == 2

        assert exp.metrics is not None
        assert exp.metrics.sensitivity == 0.0
        assert exp.metrics.specificity == 1.0

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.collect_all_result_ids",
        new_callable=AsyncMock,
    )
    async def test_re_evaluate_replaces_enriched_gene_info(
        self,
        mock_collect: AsyncMock,
        mock_get_api: AsyncMock,
    ) -> None:
        """re_evaluate_controls creates GeneInfo(id=...) without name/organism."""
        mock_collect.return_value = {"g1"}
        api = AsyncMock()
        mock_get_api.return_value = api

        exp = _exp()
        exp.true_positive_genes = [
            GeneInfo(id="g1", name="PfCRT", organism="P. falciparum", product="CRT")
        ]

        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent("plasmodb", exp)

        with patch(
            "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
            return_value=store,
        ):
            await agent.re_evaluate_controls()

        assert exp.true_positive_genes[0].id == "g1"
        assert exp.true_positive_genes[0].name is None


# ---------------------------------------------------------------------------
# Mixin protocol
# ---------------------------------------------------------------------------


class TestRefinementMixinProtocol:
    async def test_mixin_requires_site_id(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        assert agent.site_id == "plasmodb"

    async def test_mixin_get_experiment_returns_none(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent._get_experiment()
        assert result is None
