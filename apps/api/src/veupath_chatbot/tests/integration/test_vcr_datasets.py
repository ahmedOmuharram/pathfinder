"""VCR-backed integration tests for DatasetsMixin.create_dataset.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_datasets.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_datasets.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
)
from veupath_chatbot.tests.conftest import discover_gene_ids


def _id_list_config(ids: list[str]) -> WDKDatasetConfigIdList:
    return WDKDatasetConfigIdList(
        source_type="idList",
        source_content=WDKDatasetIdListContent(ids=ids),
    )


class TestCreateDataset:
    """Dataset creation via DatasetsMixin with real WDK responses."""

    @pytest.mark.vcr
    async def test_creates_dataset_and_returns_id(
        self, wdk_api: StrategyAPI,
    ) -> None:
        """Create a dataset from discovered gene IDs."""
        gene_ids = await discover_gene_ids(wdk_api, limit=2)
        assert len(gene_ids) >= 2
        config = _id_list_config(gene_ids[:2])
        ds_id = await wdk_api.create_dataset(config)

        assert isinstance(ds_id, int)
        assert ds_id > 0

    @pytest.mark.vcr
    async def test_single_gene_dataset(
        self, wdk_api: StrategyAPI,
    ) -> None:
        """Single-gene dataset returns valid ID."""
        gene_ids = await discover_gene_ids(wdk_api, limit=1)
        assert len(gene_ids) >= 1
        config = _id_list_config([gene_ids[0]])
        ds_id = await wdk_api.create_dataset(config)

        assert isinstance(ds_id, int)
        assert ds_id > 0
