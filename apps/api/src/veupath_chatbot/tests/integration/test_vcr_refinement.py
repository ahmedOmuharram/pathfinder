"""VCR-backed integration tests for AI refinement tools.

Tests refine_with_search and refine_with_gene_ids using real WDK API
calls backed by VCR cassettes. No database dependency — ExperimentStore
is used in-memory only.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_refinement.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_refinement.py -v
"""

from unittest.mock import patch

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.services.experiment.ai_refinement_tools import RefinementToolsMixin
from veupath_chatbot.services.experiment.store import ExperimentStore
from veupath_chatbot.services.experiment.types import (
    Experiment,
    ExperimentConfig,
    GeneInfo,
)
from veupath_chatbot.tests.conftest import discover_gene_ids, discover_organism

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(site_id: str, organism_param: str) -> ExperimentConfig:
    return ExperimentConfig(
        site_id=site_id,
        record_type="transcript",
        search_name="GenesByTaxon",
        parameters={"organism": organism_param},
        positive_controls=["PLACEHOLDER_POS"],
        negative_controls=["PLACEHOLDER_NEG"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
    )


def _exp(
    site_id: str,
    organism_param: str,
    exp_id: str = "exp_refine_001",
    wdk_strategy_id: int | None = None,
    wdk_step_id: int | None = None,
) -> Experiment:
    exp = Experiment(id=exp_id, config=_cfg(site_id, organism_param))
    exp.wdk_strategy_id = wdk_strategy_id
    exp.wdk_step_id = wdk_step_id
    exp.true_positive_genes = [GeneInfo(id="PLACEHOLDER_POS")]
    exp.false_negative_genes = []
    exp.false_positive_genes = []
    exp.true_negative_genes = [GeneInfo(id="PLACEHOLDER_NEG")]
    return exp


async def _create_base_strategy(
    wdk_api: StrategyAPI,
    organism_param: str,
) -> tuple[int, int]:
    """Create a real WDK strategy with one GenesByTaxon step."""
    step = await wdk_api.create_step(
        NewStepSpec(
            search_name="GenesByTaxon",
            search_config=WDKSearchConfig(
                parameters={"organism": organism_param},
            ),
            custom_name="Base step for refinement test",
        ),
        record_type="transcript",
    )
    strategy = await wdk_api.create_strategy(
        step_tree=WDKStepTree(step_id=step.id),
        name="test-refinement-base",
    )
    return strategy.id, step.id


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
    @pytest.mark.vcr
    async def test_successful_refinement(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        site_id, _base_url = wdk_test_site
        organism_param = await discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent(site_id, exp)

        with (
            patch(
                "veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api",
                return_value=wdk_api,
            ),
            patch(
                "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
                return_value=store,
            ),
        ):
            result = await agent.refine_with_search(
                search_name="GenesByTaxon",
                parameters={"organism": organism_param},
                operator="INTERSECT",
            )

        assert result["success"] is True
        assert result["newStepId"] is not None
        assert result["operator"] == "INTERSECT"
        assert result["estimatedSize"] >= 0
        assert exp.wdk_step_id == result["newStepId"]


# ---------------------------------------------------------------------------
# refine_with_gene_ids
# ---------------------------------------------------------------------------


class TestRefineWithGeneIds:
    @pytest.mark.vcr
    async def test_successful_gene_id_refinement(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        site_id, _base_url = wdk_test_site
        organism_param = await discover_organism(wdk_api)
        strategy_id, step_id = await _create_base_strategy(wdk_api, organism_param)

        # Discover real gene IDs from the assigned site
        gene_ids = await discover_gene_ids(wdk_api, limit=2)
        assert len(gene_ids) >= 2, f"Need at least 2 gene IDs from {site_id}"

        exp = _exp(site_id, organism_param, wdk_strategy_id=strategy_id, wdk_step_id=step_id)
        store = ExperimentStore()
        store.save(exp)

        agent = ConcreteRefinementAgent(site_id, exp)

        with (
            patch(
                "veupath_chatbot.services.experiment.ai_refinement_tools.get_strategy_api",
                return_value=wdk_api,
            ),
            patch(
                "veupath_chatbot.services.experiment.ai_refinement_tools.get_experiment_store",
                return_value=store,
            ),
        ):
            result = await agent.refine_with_gene_ids(
                gene_ids=gene_ids[:2],
                operator="INTERSECT",
            )

        assert result["success"] is True
        assert exp.wdk_step_id is not None
