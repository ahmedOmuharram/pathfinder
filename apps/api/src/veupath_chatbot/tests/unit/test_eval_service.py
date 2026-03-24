"""Unit tests for pure domain logic in services/eval.py.

Tests extract_gene_id() (pure function, no I/O) and fetch_all_gene_ids()
empty-result handling (pagination logic with mocked API).

WDK contract tests (fetch_all_gene_ids with real data, build_gold_strategy,
fetch_strategy_gene_ids) have been moved to integration/test_eval_service.py.
"""

from unittest.mock import AsyncMock

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKRecordInstance,
)
from veupath_chatbot.services.eval import extract_gene_id, fetch_all_gene_ids


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


class TestFetchAllGeneIdsEmptyResult:
    """Test pagination logic handles empty results correctly (mocked API)."""

    async def test_handles_empty_result(self) -> None:
        mock_api = AsyncMock()
        mock_api.get_step_answer = AsyncMock(
            return_value=WDKAnswer.model_validate(
                {"records": [], "meta": {"totalCount": 0}}
            )
        )
        result = await fetch_all_gene_ids(mock_api, 1)
        assert result == []
