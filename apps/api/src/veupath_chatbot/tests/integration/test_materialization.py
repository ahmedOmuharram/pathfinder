"""Integration tests for WDK strategy materialization.

Tests step tree materialization, strategy persistence, import, and cleanup
using real WDK API calls (backed by VCR cassettes).

Record cassettes:
    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... WDK_TARGET_SITE=plasmodb \
    uv run pytest src/veupath_chatbot/tests/integration/test_materialization.py -v --record-mode=all

Replay (CI / normal dev):
    uv run pytest src/veupath_chatbot/tests/integration/test_materialization.py -v
"""

import json
from unittest.mock import patch

import pytest

from veupath_chatbot.domain.parameters.vocab_utils import collect_leaf_terms
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKStepTree
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.experiment.materialization import (
    _materialize_step_tree,
    _persist_experiment_strategy,
    _persist_import_strategy,
    cleanup_experiment_strategy,
)
from veupath_chatbot.services.experiment.types import Experiment, ExperimentConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _discover_organism(wdk_api: StrategyAPI) -> str:
    """Query WDK to discover the first available organism for GenesByTaxon.

    Returns a JSON-encoded list with one organism term, e.g.
    ``'["Plasmodium falciparum 3D7"]'`` on plasmodb.
    """
    search_response = await wdk_api.client.get_search_details(
        "transcript", "GenesByTaxon"
    )
    for param in search_response.search_data.parameters or []:
        if param.name == "organism" and param.vocabulary is not None:
            if isinstance(param.vocabulary, dict):
                leaves = collect_leaf_terms(param.vocabulary)
                if leaves:
                    return json.dumps([leaves[0]])
            elif isinstance(param.vocabulary, list):
                for item in param.vocabulary:
                    if isinstance(item, list) and item:
                        return json.dumps([str(item[0])])
                    if isinstance(item, str):
                        return json.dumps([item])
    msg = "Could not discover organism from GenesByTaxon search parameters"
    raise RuntimeError(msg)


def _cfg(
    site_id: str,
    organism_param: str,
    mode: str = "single",
    source_strategy_id: str | None = None,
    step_tree: PlanStepNode | None = None,
) -> ExperimentConfig:
    """Build a minimal ExperimentConfig for test experiments (site-agnostic)."""
    return ExperimentConfig(
        site_id=site_id,
        record_type="transcript",
        search_name="GenesByTaxon",
        parameters={"organism": organism_param},
        positive_controls=["PF3D7_0100100"],
        negative_controls=["PF3D7_0100200"],
        controls_search_name="GeneByLocusTag",
        controls_param_name="single_gene_id",
        name="Materialization Test",
        mode=mode,
        source_strategy_id=source_strategy_id,
        step_tree=step_tree,
    )


# ---------------------------------------------------------------------------
# _materialize_step_tree
# ---------------------------------------------------------------------------


class TestMaterializeStepTree:
    @pytest.mark.vcr
    async def test_leaf_node(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """A single leaf node creates one WDK step."""
        _site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        node = PlanStepNode.model_validate(
            {
                "searchName": "GenesByTaxon",
                "parameters": {"organism": organism_param},
                "displayName": "Taxon Search",
            }
        )
        result = await _materialize_step_tree(wdk_api, node, "transcript")

        assert isinstance(result, WDKStepTree)
        assert result.step_id > 0
        assert result.primary_input is None
        assert result.secondary_input is None

    @pytest.mark.vcr
    async def test_transform_node(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """A node with primaryInput creates a transform step."""
        _site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        node = PlanStepNode.model_validate(
            {
                "searchName": "GenesByWeightFilter",
                "parameters": {
                    "min_weight": "1",
                    "max_weight": "100",
                },
                "primaryInput": {
                    "searchName": "GenesByTaxon",
                    "parameters": {"organism": organism_param},
                },
            }
        )
        result = await _materialize_step_tree(wdk_api, node, "transcript")

        assert isinstance(result, WDKStepTree)
        assert result.step_id > 0
        assert result.primary_input is not None
        assert result.primary_input.step_id > 0
        assert result.secondary_input is None
        # Transform step is different from leaf step
        assert result.step_id != result.primary_input.step_id

    @pytest.mark.vcr
    async def test_combine_node(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """A node with both primary and secondary inputs creates a combined step."""
        _site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        node = PlanStepNode.model_validate(
            {
                "searchName": "combined",
                "operator": "INTERSECT",
                "primaryInput": {
                    "searchName": "GenesByTaxon",
                    "parameters": {"organism": organism_param},
                },
                "secondaryInput": {
                    "searchName": "GenesByTaxon",
                    "parameters": {"organism": organism_param},
                },
            }
        )
        result = await _materialize_step_tree(wdk_api, node, "transcript")

        assert isinstance(result, WDKStepTree)
        assert result.step_id > 0
        assert result.primary_input is not None
        assert result.secondary_input is not None
        assert result.primary_input.step_id > 0
        assert result.secondary_input.step_id > 0
        # Combined step is different from both inputs
        assert result.step_id != result.primary_input.step_id
        assert result.step_id != result.secondary_input.step_id


# ---------------------------------------------------------------------------
# _persist_experiment_strategy
# ---------------------------------------------------------------------------


class TestPersistExperimentStrategy:
    @pytest.mark.vcr
    async def test_single_mode(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Single-mode creates one step and wraps it in a strategy."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        with patch(
            "veupath_chatbot.services.experiment.materialization.get_strategy_api",
            return_value=wdk_api,
        ):
            result = await _persist_experiment_strategy(
                _cfg(site_id, organism_param, mode="single"),
                "exp-materialize-001",
            )

        assert result["strategy_id"] > 0
        assert result["step_id"] > 0

    @pytest.mark.vcr
    async def test_multi_step_mode(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Multi-step mode materializes a step tree into a strategy."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        tree = PlanStepNode.model_validate(
            {
                "searchName": "GenesByTaxon",
                "parameters": {"organism": organism_param},
            }
        )
        with patch(
            "veupath_chatbot.services.experiment.materialization.get_strategy_api",
            return_value=wdk_api,
        ):
            result = await _persist_experiment_strategy(
                _cfg(site_id, organism_param, mode="multi-step", step_tree=tree),
                "exp-materialize-002",
            )

        assert result["strategy_id"] > 0
        assert result["step_id"] > 0


# ---------------------------------------------------------------------------
# Persist import strategy
# ---------------------------------------------------------------------------


class TestPersistImportStrategy:
    @pytest.mark.vcr
    async def test_successful_import(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Import mode duplicates an existing strategy's step tree."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        # First, create a source strategy to import from
        with patch(
            "veupath_chatbot.services.experiment.materialization.get_strategy_api",
            return_value=wdk_api,
        ):
            source_result = await _persist_experiment_strategy(
                _cfg(site_id, organism_param, mode="single"),
                "exp-source-for-import",
            )

        source_strategy_id = str(source_result["strategy_id"])

        cfg = _cfg(
            site_id,
            organism_param,
            mode="import",
            source_strategy_id=source_strategy_id,
        )
        result = await _persist_import_strategy(wdk_api, cfg, "exp-import-001")

        assert result["strategy_id"] > 0
        assert result["step_id"] > 0
        # Imported strategy should be different from source
        assert result["strategy_id"] != int(source_strategy_id)


# ---------------------------------------------------------------------------
# cleanup_experiment_strategy
# ---------------------------------------------------------------------------


class TestCleanupExperimentStrategy:
    @pytest.mark.vcr
    async def test_deletes_strategy(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Cleanup deletes the WDK strategy."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        # Create a strategy to clean up
        with patch(
            "veupath_chatbot.services.experiment.materialization.get_strategy_api",
            return_value=wdk_api,
        ):
            result = await _persist_experiment_strategy(
                _cfg(site_id, organism_param, mode="single"),
                "exp-cleanup-001",
            )

        exp = Experiment(id="exp-cleanup-001", config=_cfg(site_id, organism_param))
        exp.wdk_strategy_id = result["strategy_id"]

        with patch(
            "veupath_chatbot.services.experiment.materialization.get_strategy_api",
            return_value=wdk_api,
        ):
            await cleanup_experiment_strategy(exp)

        # Verify strategy was deleted -- attempting to fetch should fail
        with pytest.raises(WDKError):
            await wdk_api.get_strategy(result["strategy_id"])
