"""Integration tests for the thesis evaluation service (services/eval.py).

Tests gene ID fetching and gold strategy materialization using real WDK API
calls (backed by VCR cassettes).

Record cassettes:
    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... WDK_TARGET_SITE=plasmodb \
    uv run pytest src/veupath_chatbot/tests/integration/test_eval_service.py -v --record-mode=all

Replay (CI / normal dev):
    uv run pytest src/veupath_chatbot/tests/integration/test_eval_service.py -v
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from veupath_chatbot.domain.parameters.vocab_utils import collect_leaf_terms
from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    NewStepSpec,
    WDKSearchConfig,
    WDKStepTree,
)
from veupath_chatbot.services.eval import (
    build_gold_strategy,
    fetch_all_gene_ids,
    fetch_strategy_gene_ids,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _discover_organism(wdk_api: StrategyAPI) -> str:
    """Query WDK to discover the first available organism for GenesByTaxon."""
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


async def _create_strategy_with_step(
    wdk_api: StrategyAPI,
    organism_param: str,
) -> tuple[int, int]:
    """Create a real WDK strategy with one GenesByTaxon step.

    Returns (strategy_id, root_step_id).
    """
    step = await wdk_api.create_step(
        NewStepSpec(
            search_name="GenesByTaxon",
            search_config=WDKSearchConfig(
                parameters={"organism": organism_param},
            ),
            custom_name="Eval test step",
        ),
        record_type="transcript",
    )

    strategy = await wdk_api.create_strategy(
        step_tree=WDKStepTree(step_id=step.id),
        name="test-eval-base",
    )
    return strategy.id, step.id


# ---------------------------------------------------------------------------
# fetch_all_gene_ids
# ---------------------------------------------------------------------------


class TestFetchAllGeneIds:
    @pytest.mark.vcr
    async def test_fetches_gene_ids_from_real_step(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Fetches real gene IDs from a WDK step via standard report."""
        _site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        _strategy_id, step_id = await _create_strategy_with_step(
            wdk_api, organism_param
        )

        result = await fetch_all_gene_ids(wdk_api, step_id)

        assert isinstance(result, list)
        # GenesByTaxon for any organism should return at least some genes
        assert len(result) > 0
        # Each entry should be a non-empty string (gene ID)
        for gene_id in result[:10]:
            assert isinstance(gene_id, str)
            assert len(gene_id) > 0


# ---------------------------------------------------------------------------
# build_gold_strategy
# ---------------------------------------------------------------------------


class TestBuildGoldStrategy:
    @pytest.mark.vcr
    async def test_returns_gene_ids_and_wdk_ids(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """build_gold_strategy materializes a tree and returns real gene IDs."""
        site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)

        with patch(
            "veupath_chatbot.services.eval.get_strategy_api",
            return_value=wdk_api,
        ):
            result = await build_gold_strategy(
                gold_id="test_gold_integration",
                site_id=site_id,
                record_type="transcript",
                step_tree={
                    "searchName": "GenesByTaxon",
                    "parameters": {"organism": organism_param},
                },
            )

        assert result.wdk_strategy_id > 0
        assert result.root_step_id > 0
        assert isinstance(result.gene_ids, list)
        assert len(result.gene_ids) > 0
        assert result.gold_id == "test_gold_integration"


# ---------------------------------------------------------------------------
# fetch_strategy_gene_ids
# ---------------------------------------------------------------------------


class TestFetchStrategyGeneIds:
    @pytest.mark.vcr
    async def test_returns_gene_ids(
        self,
        wdk_api: StrategyAPI,
        wdk_test_site: tuple[str, str],
    ) -> None:
        """Fetches gene IDs from a real WDK strategy."""
        _site_id, _base_url = wdk_test_site
        organism_param = await _discover_organism(wdk_api)
        strategy_id, _step_id = await _create_strategy_with_step(
            wdk_api, organism_param
        )

        # Create a minimal projection-like object with wdk_strategy_id
        projection = SimpleNamespace(wdk_strategy_id=strategy_id)

        result = await fetch_strategy_gene_ids(
            api=wdk_api,
            projection=projection,
        )

        assert isinstance(result, list)
        assert len(result) > 0
        for gene_id in result[:10]:
            assert isinstance(gene_id, str)
            assert len(gene_id) > 0
