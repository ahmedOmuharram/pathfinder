"""Unit tests for AI experiment strategy refinement tools.

Tests the RefinementToolsMixin methods: refine_with_search,
refine_with_gene_ids, and re_evaluate_controls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKIdentifier,
)
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
# refine_with_search
# ---------------------------------------------------------------------------


class TestRefineWithSearch:
    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_successful_refinement(
        self, mock_spawn: MagicMock, mock_get_api: MagicMock
    ) -> None:
        api = AsyncMock()
        api.create_step.return_value = WDKIdentifier(id=200)
        api.create_combined_step.return_value = WDKIdentifier(id=300)
        api.update_strategy = AsyncMock()
        api.get_step_count.return_value = 150
        mock_get_api.return_value = api

        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent("plasmodb", exp)

        with patch(
            "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.refine_with_search(
                search_name="GenesByOrthologs",
                parameters={"organism": "pfal"},
                operator="INTERSECT",
            )

        assert result["success"] is True
        assert result["newStepId"] == 300
        assert result["operator"] == "INTERSECT"
        assert result["estimatedSize"] == 150

        # Experiment should have been updated
        assert exp.wdk_step_id == 300

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
        self, mock_get_api: MagicMock
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
# refine_with_gene_ids
# ---------------------------------------------------------------------------


class TestRefineWithGeneIds:
    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.resolve_controls_param_type",
        new_callable=AsyncMock,
        return_value="text",
    )
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_successful_gene_id_refinement(
        self,
        mock_spawn: MagicMock,
        mock_resolve: AsyncMock,
        mock_get_api: MagicMock,
    ) -> None:
        api = AsyncMock()
        api.create_step.return_value = WDKIdentifier(id=200)
        api.create_combined_step.return_value = WDKIdentifier(id=300)
        api.update_strategy = AsyncMock()
        api.get_step_count.return_value = 50
        mock_get_api.return_value = api

        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent("plasmodb", exp)

        with patch(
            "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.refine_with_gene_ids(
                gene_ids=["g1", "g2", "g3"],
                operator="INTERSECT",
            )

        assert result["success"] is True
        assert result["geneCount"] == 3
        assert exp.wdk_step_id == 300

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.resolve_controls_param_type",
        new_callable=AsyncMock,
        return_value="input-dataset",
    )
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_dataset_param_type(
        self,
        mock_spawn: MagicMock,
        mock_resolve: AsyncMock,
        mock_get_api: MagicMock,
    ) -> None:
        """When param type is input-dataset, should create a dataset first."""
        api = AsyncMock()
        api.create_dataset.return_value = 12345
        api.create_step.return_value = WDKIdentifier(id=200)
        api.create_combined_step.return_value = WDKIdentifier(id=300)
        api.update_strategy = AsyncMock()
        api.get_step_count.return_value = 50
        mock_get_api.return_value = api

        exp = _exp()
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent("plasmodb", exp)

        with patch(
            "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
            return_value=store,
        ):
            result = await agent.refine_with_gene_ids(
                gene_ids=["g1", "g2"],
                operator="UNION",
            )

        assert result["success"] is True
        expected_config = WDKDatasetConfigIdList(
            source_type="idList",
            source_content=WDKDatasetIdListContent(ids=["g1", "g2"]),
        )
        api.create_dataset.assert_awaited_once_with(expected_config)

    async def test_returns_error_when_no_experiment(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent.refine_with_gene_ids(gene_ids=["g1"])
        assert "error" in result


# ---------------------------------------------------------------------------
# re_evaluate_controls
# ---------------------------------------------------------------------------


class TestReEvaluateControls:
    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.collect_all_result_ids",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_re_evaluate_updates_metrics(
        self,
        mock_spawn: MagicMock,
        mock_collect: AsyncMock,
        mock_get_api: MagicMock,
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

        # Verify gene lists were updated
        tp_ids = {g.id for g in exp.true_positive_genes}
        fn_ids = {g.id for g in exp.false_negative_genes}
        fp_ids = {g.id for g in exp.false_positive_genes}
        tn_ids = {g.id for g in exp.true_negative_genes}

        # g1 and g3 are in result_ids AND in positive_controls -> TP
        assert tp_ids == {"g1", "g3"}
        # g2 is in positive_controls but NOT in result_ids -> FN
        assert fn_ids == {"g2"}
        # n2 is in negative_controls AND in result_ids -> FP
        assert fp_ids == {"n2"}
        # n1 is in negative_controls but NOT in result_ids -> TN
        assert tn_ids == {"n1"}

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.collect_all_result_ids",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_re_evaluate_with_empty_results(
        self,
        mock_spawn: MagicMock,
        mock_collect: AsyncMock,
        mock_get_api: MagicMock,
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

        # All positives should be FN, all negatives should be TN
        assert len(exp.true_positive_genes) == 0
        assert len(exp.false_negative_genes) == 3  # g1, g2, g3
        assert len(exp.false_positive_genes) == 0
        assert len(exp.true_negative_genes) == 2  # n1, n2

        # Check metrics consistency
        assert exp.metrics is not None
        assert exp.metrics.sensitivity == 0.0
        assert exp.metrics.specificity == 1.0

    async def test_returns_error_when_no_experiment(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent.re_evaluate_controls()
        assert "error" in result

    async def test_returns_error_when_no_step_id(self) -> None:
        exp = _exp(wdk_step_id=None)
        agent = ConcreteRefinementAgent("plasmodb", exp)
        result = await agent.re_evaluate_controls()
        assert "error" in result

    @patch("veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api")
    @patch(
        "veupath_chatbot.services.experiment.ai_refinement_tools.collect_all_result_ids",
        new_callable=AsyncMock,
    )
    @patch("veupath_chatbot.platform.store.spawn")
    async def test_re_evaluate_replaces_enriched_gene_info(
        self,
        mock_spawn: MagicMock,
        mock_collect: AsyncMock,
        mock_get_api: MagicMock,
    ) -> None:
        """re_evaluate_controls creates GeneInfo(id=...) without name/organism.

        This means previously enriched gene metadata is lost after re-evaluation.
        This is expected behavior (re-evaluation doesn't re-enrich), but
        worth documenting.
        """
        mock_collect.return_value = {"g1"}
        api = AsyncMock()
        mock_get_api.return_value = api

        exp = _exp()
        # Set up enriched gene info
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

        # After re-evaluation, gene info is bare (only ID, no metadata)
        assert exp.true_positive_genes[0].id == "g1"
        assert exp.true_positive_genes[0].name is None  # Metadata lost


# ---------------------------------------------------------------------------
# Edge cases for the mixin protocol
# ---------------------------------------------------------------------------


class TestRefinementMixinProtocol:
    async def test_mixin_requires_site_id(self) -> None:
        """The mixin requires site_id to be set."""
        agent = ConcreteRefinementAgent("plasmodb", None)
        assert agent.site_id == "plasmodb"

    async def test_mixin_get_experiment_returns_none(self) -> None:
        agent = ConcreteRefinementAgent("plasmodb", None)
        result = await agent._get_experiment()
        assert result is None
