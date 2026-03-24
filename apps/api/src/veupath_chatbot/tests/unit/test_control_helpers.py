"""Tests for control_helpers module."""

import json
from unittest.mock import AsyncMock

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordInstance,
    WDKStrategySummary,
)
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.control_helpers import (
    _encode_id_list,
    _get_total_count_for_step,
    cleanup_internal_control_test_strategies,
    delete_temp_strategy,
)
from veupath_chatbot.services.wdk.helpers import extract_record_ids

# ---------------------------------------------------------------------------
# _encode_id_list
# ---------------------------------------------------------------------------


class TestEncodeIdList:
    def test_newline_format(self) -> None:
        result = _encode_id_list(["a", "b", "c"], "newline")
        assert result == "a\nb\nc"

    def test_comma_format(self) -> None:
        result = _encode_id_list(["a", "b", "c"], "comma")
        assert result == "a,b,c"

    def test_json_list_format(self) -> None:
        result = _encode_id_list(["a", "b", "c"], "json_list")
        assert json.loads(result) == ["a", "b", "c"]

    def test_strips_whitespace(self) -> None:
        result = _encode_id_list(["  a  ", "  b  "], "newline")
        assert result == "a\nb"

    def test_filters_empty_strings(self) -> None:
        result = _encode_id_list(["a", "", "  ", "b"], "comma")
        assert result == "a,b"

    def test_empty_list(self) -> None:
        result = _encode_id_list([], "newline")
        assert result == ""


# ---------------------------------------------------------------------------
# delete_temp_strategy
# ---------------------------------------------------------------------------


class TestDeleteTempStrategy:
    async def test_swallows_errors(self) -> None:
        api = AsyncMock()
        api.delete_strategy.side_effect = WDKError(detail="WDK error")
        # Should not raise
        await delete_temp_strategy(api, 42)


# ---------------------------------------------------------------------------
# extract_record_ids
# ---------------------------------------------------------------------------


class TestExtractRecordIds:
    def test_extracts_from_primary_key(self) -> None:
        records = [
            WDKRecordInstance(id=[{"name": "gene_source_id", "value": "PF3D7_1234"}]),
            WDKRecordInstance(id=[{"name": "gene_source_id", "value": "PF3D7_5678"}]),
        ]
        assert extract_record_ids(records) == ["PF3D7_1234", "PF3D7_5678"]

    def test_extracts_from_preferred_key(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "gene_source_id", "value": "PK_VALUE"}],
                attributes={"custom_id": "CUSTOM_VALUE"},
            ),
        ]
        result = extract_record_ids(records, preferred_key="custom_id")
        assert result == ["CUSTOM_VALUE"]

    def test_falls_back_to_pk_when_preferred_missing(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "gene_source_id", "value": "PK_VALUE"}],
                attributes={"other": "not_it"},
            ),
        ]
        result = extract_record_ids(records, preferred_key="custom_id")
        assert result == ["PK_VALUE"]

    def test_empty_list(self) -> None:
        assert extract_record_ids([]) == []

    def test_skips_blank_values(self) -> None:
        records = [
            WDKRecordInstance(id=[{"name": "x", "value": "  "}]),
            WDKRecordInstance(id=[{"name": "x", "value": "valid"}]),
        ]
        result = extract_record_ids(records)
        assert result == ["valid"]

    def test_empty_pk_array(self) -> None:
        records = [WDKRecordInstance(id=[])]
        assert extract_record_ids(records) == []


# ---------------------------------------------------------------------------
# _get_total_count_for_step
# ---------------------------------------------------------------------------


class TestGetTotalCountForStep:
    async def test_returns_count(self) -> None:
        api = AsyncMock()
        api.get_step_count.return_value = 42
        result = await _get_total_count_for_step(api, 1)
        assert result == 42

    async def test_returns_none_on_error(self) -> None:
        api = AsyncMock()
        api.get_step_count.side_effect = WDKError(detail="fail")
        result = await _get_total_count_for_step(api, 1)
        assert result is None


# ---------------------------------------------------------------------------
# cleanup_internal_control_test_strategies
# ---------------------------------------------------------------------------


class TestCleanupInternalControlTestStrategies:
    @staticmethod
    def _summary(strategy_id: int = 100, name: str = "Test") -> WDKStrategySummary:
        return WDKStrategySummary(
            strategy_id=strategy_id,
            name=name,
            root_step_id=1,
        )

    async def test_swallows_delete_errors(self) -> None:
        api = AsyncMock()
        api.delete_strategy.side_effect = WDKError(detail="WDK error")
        items = [
            self._summary(100, "__pathfinder_internal__:Pathfinder control test A"),
        ]
        # Should not raise
        await cleanup_internal_control_test_strategies(api, items)
