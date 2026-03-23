"""Tests for the thesis evaluation service (services/eval.py).

Extracted business logic: gene ID fetching, root step extraction, strategy
validation -- all previously living in the transport router.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKIdentifier,
    WDKRecordInstance,
    WDKStrategyDetails,
)
from veupath_chatbot.services.eval import (
    build_gold_strategy,
    extract_gene_id,
    fetch_all_gene_ids,
    fetch_strategy_gene_ids,
)

# ---------------------------------------------------------------------------
# extract_gene_id
# ---------------------------------------------------------------------------


class TestExtractGeneId:
    def test_extracts_source_id(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id", "value": "PF3D7_0100100"}])
        assert extract_gene_id(record) == "PF3D7_0100100"

    def test_extracts_gene_source_id(self) -> None:
        record = WDKRecordInstance(
            id=[{"name": "gene_source_id", "value": "PF3D7_0200300"}]
        )
        assert extract_gene_id(record) == "PF3D7_0200300"

    def test_fallback_to_first_value(self) -> None:
        record = WDKRecordInstance(id=[{"name": "other_field", "value": "GENE_XYZ"}])
        assert extract_gene_id(record) == "GENE_XYZ"

    def test_returns_none_for_empty_id(self) -> None:
        record = WDKRecordInstance(id=[])
        assert extract_gene_id(record) is None

    def test_returns_none_for_default_id(self) -> None:
        record = WDKRecordInstance()
        assert extract_gene_id(record) is None


# ---------------------------------------------------------------------------
# fetch_all_gene_ids
# ---------------------------------------------------------------------------


class TestFetchAllGeneIds:
    @pytest.mark.asyncio
    async def test_fetches_single_page(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_step_answer = AsyncMock(
            return_value=WDKAnswer.model_validate(
                {
                    "records": [
                        {"id": [{"name": "source_id", "value": "GENE_A"}]},
                        {"id": [{"name": "source_id", "value": "GENE_B"}]},
                    ],
                    "meta": {"totalCount": 2},
                }
            )
        )
        result = await fetch_all_gene_ids(mock_api, 1)
        assert result == ["GENE_A", "GENE_B"]

    @pytest.mark.asyncio
    async def test_handles_empty_result(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_step_answer = AsyncMock(
            return_value=WDKAnswer.model_validate(
                {"records": [], "meta": {"totalCount": 0}}
            )
        )
        result = await fetch_all_gene_ids(mock_api, 1)
        assert result == []


# ---------------------------------------------------------------------------
# build_gold_strategy
# ---------------------------------------------------------------------------


class TestBuildGoldStrategy:
    @pytest.mark.asyncio
    async def test_returns_gene_ids_and_wdk_ids(self) -> None:
        mock_api = AsyncMock()
        mock_tree = MagicMock()
        mock_tree.step_id = 42

        mock_api.create_strategy = AsyncMock(return_value=WDKIdentifier(id=123))
        mock_api.get_step_answer = AsyncMock(
            return_value=WDKAnswer.model_validate(
                {
                    "records": [
                        {"id": [{"name": "source_id", "value": "GENE_A"}]},
                    ],
                    "meta": {"totalCount": 1},
                }
            )
        )

        with (
            patch(
                "veupath_chatbot.services.eval.get_strategy_api",
                return_value=mock_api,
            ),
            patch(
                "veupath_chatbot.services.eval._materialize_step_tree",
                new_callable=AsyncMock,
                return_value=mock_tree,
            ),
        ):
            result = await build_gold_strategy(
                gold_id="test_gold",
                site_id="plasmodb",
                record_type="gene",
                step_tree={"searchName": "GenesByTaxon"},
            )

        assert result.wdk_strategy_id == 123
        assert result.root_step_id == 42
        assert result.gene_ids == ["GENE_A"]


# ---------------------------------------------------------------------------
# fetch_strategy_gene_ids
# ---------------------------------------------------------------------------


class TestFetchStrategyGeneIds:
    @pytest.mark.asyncio
    async def test_returns_gene_ids(self) -> None:
        mock_strategy = WDKStrategyDetails.model_validate(
            {
                "strategyId": 42,
                "name": "Test",
                "rootStepId": 99,
                "stepTree": {"stepId": 99},
            }
        )

        mock_api = AsyncMock()
        mock_api.get_strategy = AsyncMock(return_value=mock_strategy)
        mock_api.get_step_answer = AsyncMock(
            return_value=WDKAnswer.model_validate(
                {
                    "records": [
                        {"id": [{"name": "source_id", "value": "GENE_X"}]},
                    ],
                    "meta": {"totalCount": 1},
                }
            )
        )

        mock_projection = MagicMock()
        mock_projection.wdk_strategy_id = 42

        result = await fetch_strategy_gene_ids(
            api=mock_api,
            projection=mock_projection,
        )

        assert result == ["GENE_X"]
        mock_api.get_strategy.assert_awaited_once_with(42)
