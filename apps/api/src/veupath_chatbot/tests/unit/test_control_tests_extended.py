"""Extended edge-case tests for control_tests and control_helpers.

Covers:
- Control set has same genes as test set (overlap)
- Control set is empty
- Control set has duplicates
- _encode_id_list edge cases
- extract_record_ids edge cases
- _extract_intersection_data edge cases
- run_positive_negative_controls edge cases
"""

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKSearchResponse,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_helpers import _encode_id_list
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    _extract_intersection_data,
    _run_intersection_control,
    run_positive_negative_controls,
)
from veupath_chatbot.services.wdk.helpers import extract_record_ids


@dataclass
class _MockApiIds:
    """Mock WDK API return IDs for _make_mock_api."""

    create_step_id: int = 100
    create_combined_step_id: int = 200
    create_strategy_id: int = 300
    create_dataset_id: int = 999


def _make_search_response(raw: JSONObject) -> WDKSearchResponse:
    """Wrap a raw search details dict in a WDKSearchResponse."""
    search_data = dict(raw.get("searchData", {}))
    if "urlSegment" not in search_data:
        search_data["urlSegment"] = "MockSearch"
    wrapped: JSONObject = {
        "searchData": search_data,
        "validation": raw.get("validation", {"level": "DISPLAYABLE", "isValid": True}),
    }
    return WDKSearchResponse.model_validate(wrapped)


def _make_mock_api(
    *,
    step_count: int = 42,
    step_answer: JSONObject | None = None,
    search_details: JSONObject | None = None,
    ids: _MockApiIds | None = None,
) -> AsyncMock:
    """Build an AsyncMock that behaves like StrategyAPI."""
    mock_ids = ids or _MockApiIds()
    api = AsyncMock(spec=StrategyAPI)
    api.get_step_count = AsyncMock(return_value=step_count)
    default_answer_raw = step_answer or {
        "meta": {"totalCount": step_count},
        "records": [],
    }
    api.get_step_answer = AsyncMock(
        return_value=WDKAnswer.model_validate(default_answer_raw)
    )
    api.create_step = AsyncMock(return_value={"id": mock_ids.create_step_id})
    api.create_combined_step = AsyncMock(
        return_value={"id": mock_ids.create_combined_step_id}
    )
    api.create_strategy = AsyncMock(return_value={"id": mock_ids.create_strategy_id})
    api.delete_strategy = AsyncMock(return_value=None)
    api.list_strategies = AsyncMock(return_value=[])
    api.create_dataset = AsyncMock(return_value=mock_ids.create_dataset_id)
    api.client = MagicMock()
    raw_details = search_details or {
        "searchData": {
            "urlSegment": "GeneByLocusTag",
            "parameters": [
                {"name": "ds_gene_ids", "type": "input-dataset"},
            ],
        },
    }
    api.client.get_search_details = AsyncMock(
        return_value=_make_search_response(raw_details),
    )
    return api


# ---------------------------------------------------------------------------
# _encode_id_list edge cases
# ---------------------------------------------------------------------------


class TestEncodeIdListEdgeCases:
    def test_all_whitespace_ids(self) -> None:
        """All whitespace IDs should produce empty output."""
        result = _encode_id_list(["  ", "\t", "\n"], "newline")
        assert result == ""

    def test_json_list_with_special_chars(self) -> None:
        """IDs with special characters should be properly JSON-encoded."""
        result = _encode_id_list(['a"b', "c'd"], "json_list")
        parsed = json.loads(result)
        assert parsed == ['a"b', "c'd"]

    def test_comma_format_with_commas_in_ids(self) -> None:
        """IDs containing commas would be ambiguous in comma format."""
        result = _encode_id_list(["a,b", "c"], "comma")
        # The function doesn't escape -- this documents current behavior
        assert result == "a,b,c"

    def test_newline_format_with_newlines_in_ids(self) -> None:
        """IDs containing newlines would be ambiguous in newline format."""
        result = _encode_id_list(["a\nb", "c"], "newline")
        # The function doesn't escape -- this documents current behavior
        assert result == "a\nb\nc"

    def test_duplicate_ids_not_deduplicated(self) -> None:
        """Duplicate IDs are NOT deduplicated by _encode_id_list."""
        result = _encode_id_list(["a", "a", "b"], "newline")
        assert result == "a\na\nb"

    def test_single_id(self) -> None:
        result = _encode_id_list(["only_one"], "newline")
        assert result == "only_one"


# ---------------------------------------------------------------------------
# extract_record_ids edge cases
# ---------------------------------------------------------------------------


class TestExtractRecordIdsEdgeCases:
    def test_preferred_key_with_empty_value(self) -> None:
        """Preferred key with empty string falls back to PK."""
        records = [
            {
                "id": [{"name": "x", "value": "PK_VAL"}],
                "attributes": {"custom": ""},
            }
        ]
        result = extract_record_ids(records, preferred_key="custom")
        assert result == ["PK_VAL"]

    def test_preferred_key_with_whitespace_value(self) -> None:
        """Preferred key with whitespace-only value falls back to PK."""
        records = [
            {
                "id": [{"name": "x", "value": "PK_VAL"}],
                "attributes": {"custom": "   "},
            }
        ]
        result = extract_record_ids(records, preferred_key="custom")
        assert result == ["PK_VAL"]

    def test_no_attributes_key(self) -> None:
        """Record without attributes key still extracts from PK."""
        records = [
            {"id": [{"name": "x", "value": "PK_VAL"}]},
        ]
        result = extract_record_ids(records, preferred_key="custom")
        assert result == ["PK_VAL"]

    def test_pk_element_with_non_dict_first(self) -> None:
        """Non-dict first PK element should be handled."""
        records = [
            {"id": ["not_a_dict"]},
        ]
        result = extract_record_ids(records)
        assert result == []

    def test_multiple_pk_elements_takes_first_valid(self) -> None:
        """When there are multiple PK elements, takes the first valid one."""
        records = [
            {
                "id": [
                    {"name": "x", "value": "FIRST"},
                    {"name": "y", "value": "SECOND"},
                ],
            },
        ]
        result = extract_record_ids(records)
        assert result == ["FIRST"]

    def test_duplicate_ids_from_records(self) -> None:
        """Duplicate IDs from different records are all returned."""
        records = [
            {"id": [{"name": "x", "value": "SAME"}]},
            {"id": [{"name": "x", "value": "SAME"}]},
        ]
        result = extract_record_ids(records)
        assert result == ["SAME", "SAME"]


# ---------------------------------------------------------------------------
# _extract_intersection_data edge cases
# ---------------------------------------------------------------------------


class TestExtractIntersectionDataEdgeCases:
    def test_empty_payload(self) -> None:
        count, ids, has_ids = _extract_intersection_data({})
        assert count == 0
        assert ids == set()
        assert has_ids is False

    def test_count_as_float(self) -> None:
        """intersectionCount as float should be converted to int."""
        count, _ids, _has_ids = _extract_intersection_data({"intersectionCount": 5.7})
        assert count == 5

    def test_count_as_string_fallback(self) -> None:
        """intersectionCount as string should default to 0."""
        count, _ids, _has_ids = _extract_intersection_data(
            {"intersectionCount": "not_a_number"}
        )
        assert count == 0

    def test_intersection_ids_none(self) -> None:
        """intersectionIds=None should report has_ids=False."""
        count, _ids, has_ids = _extract_intersection_data(
            {"intersectionCount": 5, "intersectionIds": None}
        )
        assert count == 5
        assert has_ids is False

    def test_intersection_ids_with_none_elements(self) -> None:
        """None elements in intersectionIds should be excluded from set."""
        _count, ids, has_ids = _extract_intersection_data(
            {"intersectionCount": 3, "intersectionIds": ["A", None, "B"]}
        )
        assert ids == {"A", "B"}
        assert has_ids is True

    def test_intersection_ids_empty_list(self) -> None:
        """Empty intersectionIds list: has_ids=True but empty set."""
        _count, ids, has_ids = _extract_intersection_data(
            {"intersectionCount": 0, "intersectionIds": []}
        )
        assert ids == set()
        assert has_ids is True


# ---------------------------------------------------------------------------
# Control set same genes as test set
# ---------------------------------------------------------------------------


class TestControlsOverlapWithTarget:
    """When control set genes overlap with target results."""

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_all_positives_found(self, mock_get_api: MagicMock) -> None:
        """All positive controls found in target -- recall should be 1.0.

        get_step_count is called twice:
        1) For the target step -> returns target result count (e.g. 100)
        2) For the combined (intersection) step -> returns intersection count
        We mock it to return different values for each call.
        """
        pos_ids = ["G1", "G2", "G3"]
        api = _make_mock_api(
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 3},
                "records": [
                    {"id": [{"name": "id", "value": "G1"}]},
                    {"id": [{"name": "id", "value": "G2"}]},
                    {"id": [{"name": "id", "value": "G3"}]},
                ],
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        # First call: target count (100), second call: intersection count (3)
        api.get_step_count = AsyncMock(side_effect=[100, 3])
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, positive_controls=pos_ids, skip_cleanup=True
        )

        pos_result = result.get("positive")
        assert isinstance(pos_result, dict)
        assert pos_result["recall"] == 1.0
        assert pos_result["missingIdsSample"] == []


# ---------------------------------------------------------------------------
# Control set is empty
# ---------------------------------------------------------------------------


class TestEmptyControlSets:
    """Edge cases where control sets are empty."""

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_empty_positive_controls(self, mock_get_api: MagicMock) -> None:
        """Empty positive controls list should be treated as no positives."""
        api = _make_mock_api()
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, positive_controls=[], skip_cleanup=True
        )

        assert result["positive"] is None
        api.create_step.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_empty_negative_controls(self, mock_get_api: MagicMock) -> None:
        """Empty negative controls list should be treated as no negatives."""
        api = _make_mock_api()
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, negative_controls=[], skip_cleanup=True
        )

        assert result["negative"] is None
        api.create_step.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_whitespace_only_controls_filtered(
        self, mock_get_api: MagicMock
    ) -> None:
        """Controls that are only whitespace should be filtered out."""
        api = _make_mock_api()
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, positive_controls=["  ", "\t", ""], skip_cleanup=True
        )

        # All filtered out -> no positives
        assert result["positive"] is None
        api.create_step.assert_not_awaited()


# ---------------------------------------------------------------------------
# Control set has duplicates
# ---------------------------------------------------------------------------


class TestDuplicateControls:
    """Edge cases where control sets contain duplicate gene IDs."""

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_duplicate_positives_counted_correctly(
        self, mock_get_api: MagicMock
    ) -> None:
        """Duplicate positive controls: controlsCount should include dupes."""
        api = _make_mock_api(
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 1},
                "records": [
                    {"id": [{"name": "id", "value": "G1"}]},
                ],
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        # target count = 50, intersection count = 1
        api.get_step_count = AsyncMock(side_effect=[50, 1])
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, positive_controls=["G1", "G1", "G2"], skip_cleanup=True
        )

        pos = result.get("positive")
        assert isinstance(pos, dict)
        # controlsCount is len of cleaned IDs which includes duplicates
        assert pos["controlsCount"] == 3

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_duplicate_negatives(self, mock_get_api: MagicMock) -> None:
        """Duplicate negative controls should all be sent to WDK."""
        api = _make_mock_api(
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 0},
                "records": [],
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        # target count = 50, intersection count = 0
        api.get_step_count = AsyncMock(side_effect=[50, 0])
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, negative_controls=["NEG1", "NEG1"], skip_cleanup=True
        )

        neg = result.get("negative")
        assert isinstance(neg, dict)
        assert neg["controlsCount"] == 2
        assert neg["falsePositiveRate"] == 0.0


# ---------------------------------------------------------------------------
# Recall and false positive rate calculations
# ---------------------------------------------------------------------------


class TestRecallAndFPR:
    """Edge cases for recall and false positive rate calculations."""

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_zero_intersection_recall(self, mock_get_api: MagicMock) -> None:
        """No overlap -> recall = 0."""
        api = _make_mock_api(
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 0},
                "records": [],
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        # target count = 50, intersection count = 0
        api.get_step_count = AsyncMock(side_effect=[50, 0])
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, positive_controls=["G1", "G2"], skip_cleanup=True
        )

        pos = result.get("positive")
        assert isinstance(pos, dict)
        assert pos["recall"] == 0.0

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_full_false_positive_rate(self, mock_get_api: MagicMock) -> None:
        """All negatives found -> FPR = 1.0."""
        api = _make_mock_api(
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 2},
                "records": [
                    {"id": [{"name": "id", "value": "NEG1"}]},
                    {"id": [{"name": "id", "value": "NEG2"}]},
                ],
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        # target count = 100, intersection count = 2
        api.get_step_count = AsyncMock(side_effect=[100, 2])
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_value_format="newline",
        )
        result = await run_positive_negative_controls(
            _cfg, negative_controls=["NEG1", "NEG2"], skip_cleanup=True
        )

        neg = result.get("negative")
        assert isinstance(neg, dict)
        assert neg["falsePositiveRate"] == 1.0


# ---------------------------------------------------------------------------
# _run_intersection_control with controls_extra_parameters
# ---------------------------------------------------------------------------


class TestControlsExtraParams:
    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_extra_params_merged(self, mock_get_api: MagicMock) -> None:
        """Extra parameters should be merged into the controls step."""
        api = _make_mock_api(
            search_details={
                "searchData": {
                    "parameters": [
                        {"name": "gene_list", "type": "string"},
                    ]
                }
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        mock_get_api.return_value = api

        await _run_intersection_control(
            IntersectionConfig(
                site_id="plasmodb",
                record_type="transcript",
                target_search_name="Search",
                target_parameters={},
                controls_search_name="ControlSearch",
                controls_param_name="gene_list",
                controls_value_format="newline",
                controls_extra_parameters={"organism": "Pf"},
            ),
            controls_ids=["A"],
        )

        # Check the controls step got both the gene list AND the extra param
        controls_call_kwargs = api.create_step.call_args_list[1][1]
        assert controls_call_kwargs["parameters"]["gene_list"] == "A"
        assert controls_call_kwargs["parameters"]["organism"] == "Pf"

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_none_extra_params(self, mock_get_api: MagicMock) -> None:
        """None extra params should not crash."""
        api = _make_mock_api(
            search_details={
                "searchData": {
                    "parameters": [
                        {"name": "gene_list", "type": "string"},
                    ]
                }
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        mock_get_api.return_value = api

        await _run_intersection_control(
            IntersectionConfig(
                site_id="plasmodb",
                record_type="transcript",
                target_search_name="Search",
                target_parameters={},
                controls_search_name="ControlSearch",
                controls_param_name="gene_list",
                controls_value_format="newline",
            ),
            controls_ids=["A"],
        )

        controls_call_kwargs = api.create_step.call_args_list[1][1]
        assert "gene_list" in controls_call_kwargs["parameters"]
