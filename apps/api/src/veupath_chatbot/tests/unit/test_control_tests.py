"""Tests for veupath_chatbot.services.control_tests.

All WDK calls are mocked. These tests validate:
- get_step_answer uses POST /reports/standard (not GET /answer)
- get_step_count uses POST /reports/standard
- _get_total_count_for_step wraps get_step_count correctly
- _run_intersection_control wires steps, creates strategy, fetches answer
- resolve_controls_param_type correctly detects input-dataset params
- extract_record_ids extracts IDs from WDK answer records
- _encode_id_list formats correctly
- run_positive_negative_controls composes results
- dataset creation path for input-dataset params
"""

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pydantic
import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKDatasetConfigIdList,
    WDKDatasetIdListContent,
    WDKIdentifier,
    WDKRecordInstance,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import DataParsingError, WDKError
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_helpers import (
    _encode_id_list,
    _get_total_count_for_step,
)
from veupath_chatbot.services.control_tests import (
    IntersectionConfig,
    _run_intersection_control,
    resolve_controls_param_type,
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
    """Wrap a raw search details dict in a WDKSearchResponse.

    Ensures ``searchData.urlSegment`` and ``validation`` are present.
    """
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
    """Build an AsyncMock that behaves like StrategyAPI.

    :param step_count: Number of mock steps (default: 42).
    :param step_answer: Mock step answer payload (default: None).
    :param search_details: Mock search details (default: None).
    :param ids: Mock WDK step/strategy return IDs (default: _MockApiIds()).

    """
    mock_ids = ids or _MockApiIds()
    api = AsyncMock(spec=StrategyAPI)

    # get_step_count returns an int
    api.get_step_count = AsyncMock(return_value=step_count)

    # get_step_answer returns WDKAnswer with meta + records
    default_answer_raw = step_answer or {
        "meta": {"totalCount": step_count},
        "records": [
            {
                "id": [{"name": "source_id", "value": "PF3D7_001"}],
                "attributes": {"source_id": "PF3D7_001"},
            },
            {
                "id": [{"name": "source_id", "value": "PF3D7_002"}],
                "attributes": {"source_id": "PF3D7_002"},
            },
        ],
    }
    api.get_step_answer = AsyncMock(
        return_value=WDKAnswer.model_validate(default_answer_raw)
    )

    # create_step returns WDKIdentifier
    api.create_step = AsyncMock(return_value=WDKIdentifier(id=mock_ids.create_step_id))

    # create_combined_step returns WDKIdentifier
    api.create_combined_step = AsyncMock(
        return_value=WDKIdentifier(id=mock_ids.create_combined_step_id)
    )

    # create_strategy returns WDKIdentifier
    api.create_strategy = AsyncMock(
        return_value=WDKIdentifier(id=mock_ids.create_strategy_id)
    )

    # delete_strategy succeeds
    api.delete_strategy = AsyncMock(return_value=None)
    api.list_strategies = AsyncMock(return_value=[])

    # create_dataset returns dataset ID
    api.create_dataset = AsyncMock(return_value=mock_ids.create_dataset_id)

    # client.get_search_details returns typed WDKSearchResponse
    api.client = MagicMock()
    raw_details = search_details or {
        "searchData": {
            "urlSegment": "GeneByLocusTag",
            "parameters": [
                {"name": "ds_gene_ids", "type": "input-dataset"},
                {"name": "other_param", "type": "string"},
            ],
        },
    }
    api.client.get_search_details = AsyncMock(
        return_value=_make_search_response(raw_details),
    )

    return api


class TestEncodeIdList:
    def test_newline_format(self) -> None:
        result = _encode_id_list(["A", "B", "C"], "newline")
        assert result == "A\nB\nC"

    def test_comma_format(self) -> None:
        result = _encode_id_list(["A", "B", "C"], "comma")
        assert result == "A,B,C"

    def test_json_list_format(self) -> None:
        result = _encode_id_list(["A", "B"], "json_list")
        assert json.loads(result) == ["A", "B"]

    def test_strips_whitespace(self) -> None:
        result = _encode_id_list(["  A ", " B  "], "newline")
        assert result == "A\nB"

    def test_skips_empty_ids(self) -> None:
        result = _encode_id_list(["A", "", "  ", "B"], "newline")
        assert result == "A\nB"


class TestExtractRecordIds:
    def test_extracts_from_wdk_id_key(self) -> None:
        """WDK StandardReporter uses ``"id"`` for the primary key array."""
        records = [
            WDKRecordInstance(id=[{"name": "source_id", "value": "GENE1"}]),
            WDKRecordInstance(id=[{"name": "source_id", "value": "GENE2"}]),
        ]
        assert extract_record_ids(records) == ["GENE1", "GENE2"]

    def test_extracts_from_preferred_key(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PK1"}],
                attributes={"gene_id": "ATTR1"},
            ),
        ]
        assert extract_record_ids(records, preferred_key="gene_id") == ["ATTR1"]

    def test_falls_back_to_id_when_preferred_missing(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PK1"}],
                attributes={"other": "X"},
            ),
        ]
        assert extract_record_ids(records, preferred_key="gene_id") == ["PK1"]

    def test_empty_list_returns_empty(self) -> None:
        assert extract_record_ids([]) == []

    def test_empty_pk_array_skipped(self) -> None:
        records = [
            WDKRecordInstance(id=[]),
            WDKRecordInstance(id=[{"name": "source_id", "value": "GOOD"}]),
        ]
        assert extract_record_ids(records) == ["GOOD"]

    def test_composite_primary_key_extracts_first(self) -> None:
        """For composite keys (e.g., transcript), first PK value is extracted."""
        records = [
            WDKRecordInstance(
                id=[
                    {"name": "source_id", "value": "PF3D7_0209000"},
                    {"name": "project_id", "value": "PlasmoDB"},
                ],
            ),
        ]
        assert extract_record_ids(records) == ["PF3D7_0209000"]


class TestGetTotalCountForStep:
    @pytest.mark.asyncio
    async def test_returns_count_on_success(self) -> None:
        api = _make_mock_api(step_count=123)
        result = await _get_total_count_for_step(api, 42)
        assert result == 123

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        api = _make_mock_api()
        api.get_step_count = AsyncMock(side_effect=WDKError(detail="WDK error"))
        result = await _get_total_count_for_step(api, 42)
        assert result is None


class TestResolveControlsParamType:
    @pytest.mark.asyncio
    async def test_detects_input_dataset(self) -> None:
        api = _make_mock_api()
        result = await resolve_controls_param_type(
            api, "transcript", "GeneByLocusTag", "ds_gene_ids"
        )
        assert result == "input-dataset"

    @pytest.mark.asyncio
    async def test_detects_string_param(self) -> None:
        api = _make_mock_api()
        result = await resolve_controls_param_type(
            api, "transcript", "GeneByLocusTag", "other_param"
        )
        assert result == "string"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_param(self) -> None:
        api = _make_mock_api()
        result = await resolve_controls_param_type(
            api, "transcript", "GeneByLocusTag", "nonexistent"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        api = _make_mock_api()
        api.client.get_search_details = AsyncMock(
            side_effect=WDKError(detail="network error")
        )
        result = await resolve_controls_param_type(
            api, "transcript", "GeneByLocusTag", "ds_gene_ids"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_malformed_response(self) -> None:
        api = _make_mock_api(search_details={"unexpected": "format"})
        result = await resolve_controls_param_type(
            api, "transcript", "GeneByLocusTag", "ds_gene_ids"
        )
        assert result is None


class TestRunIntersectionControl:
    """Tests for _run_intersection_control.

    The function now creates its own target step internally (each call gets a
    fresh target step) to avoid WDK cascade-delete issues.


    """

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_full_flow_with_dataset_upload(self, mock_get_api: MagicMock) -> None:
        """When controls param is input-dataset, upload dataset and use its ID."""
        # create_step is called TWICE: once for target, once for controls.
        # Return different IDs for each call.
        target_step_resp = WDKIdentifier(id=50)
        controls_step_resp = WDKIdentifier(id=51)
        api = _make_mock_api(
            step_count=3,
            ids=_MockApiIds(
                create_combined_step_id=60,
                create_strategy_id=70,
                create_dataset_id=12345,
            ),
            step_answer={
                "meta": {"totalCount": 3},
                "records": [
                    {"id": [{"name": "source_id", "value": "PF3D7_001"}]},
                    {"id": [{"name": "source_id", "value": "PF3D7_002"}]},
                    {"id": [{"name": "source_id", "value": "PF3D7_003"}]},
                ],
            },
        )
        api.create_step = AsyncMock(side_effect=[target_step_resp, controls_step_resp])
        mock_get_api.return_value = api

        result = await _run_intersection_control(
            IntersectionConfig(
                site_id="plasmodb",
                record_type="transcript",
                target_search_name="GenesByRNASeq",
                target_parameters={"fold_change": "2"},
                controls_search_name="GeneByLocusTag",
                controls_param_name="ds_gene_ids",
            ),
            controls_ids=["PF3D7_001", "PF3D7_002", "PF3D7_003"],
        )

        # Result shape
        assert result["controlsCount"] == 3
        assert result["intersectionCount"] == 3
        assert result["targetStepId"] == 50
        assert result["targetEstimatedSize"] == 3
        assert result["intersectionIds"] == [
            "PF3D7_001",
            "PF3D7_002",
            "PF3D7_003",
        ]

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_cleanup_on_answer_failure(self, mock_get_api: MagicMock) -> None:
        """Strategy is cleaned up even if get_step_answer fails."""
        api = _make_mock_api()
        api.create_step = AsyncMock(
            side_effect=[WDKIdentifier(id=10), WDKIdentifier(id=11)]
        )
        api.get_step_answer = AsyncMock(side_effect=Exception("WDK boom"))
        mock_get_api.return_value = api

        with pytest.raises(Exception, match="WDK boom"):
            await _run_intersection_control(
                IntersectionConfig(
                    site_id="plasmodb",
                    record_type="transcript",
                    target_search_name="GenesByRNASeq",
                    target_parameters={},
                    controls_search_name="GeneByLocusTag",
                    controls_param_name="ds_gene_ids",
                ),
                controls_ids=["A"],
            )

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_each_call_creates_own_target_step(
        self, mock_get_api: MagicMock
    ) -> None:
        """Verify each call creates its own target step (no sharing)."""
        call_count = 0

        async def _create_step_side_effect(*args: Any, **kwargs: Any) -> WDKIdentifier:
            nonlocal call_count
            call_count += 1
            return WDKIdentifier(id=call_count * 10)

        api = _make_mock_api()
        api.create_step = AsyncMock(side_effect=_create_step_side_effect)
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={"fold_change": "2"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        # First call
        r1 = await _run_intersection_control(_cfg, controls_ids=["POS1"])
        assert r1["targetStepId"] == 10  # first create_step call

        # Second call (simulating negative controls after positive)
        r2 = await _run_intersection_control(_cfg, controls_ids=["NEG1"])
        assert r2["targetStepId"] == 30  # third create_step call (new target)


class TestStrategyAPIGetStepAnswer:
    """Verify get_step_answer calls POST /reports/standard, NOT GET /answer."""

    @pytest.mark.asyncio
    async def test_uses_post_reports_standard(self) -> None:
        """get_step_answer should POST to /reports/standard."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value={
                "meta": {"totalCount": 5},
                "records": [],
            }
        )

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api._resolved_user_id = "12345"
        api._session_initialized = True  # bypass _ensure_session

        result = await api.get_step_answer(
            step_id=999,
            pagination={"offset": 0, "numRecords": 10},
        )

        assert result.meta.total_count == 5
        assert result.records == []



class TestStrategyAPIGetStepCount:
    @pytest.mark.asyncio
    async def test_returns_total_count(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value={"meta": {"totalCount": 42}, "records": []}
        )

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api._resolved_user_id = "12345"
        with patch.object(api, "_ensure_session", AsyncMock()):
            result = await api.get_step_count(step_id=999)
        assert result == 42

    @pytest.mark.asyncio
    async def test_raises_on_missing_meta(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"records": []})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api._resolved_user_id = "12345"
        with (
            patch.object(api, "_ensure_session", AsyncMock()),
            pytest.raises(DataParsingError, match="Unexpected WDK answer"),
        ):
            await api.get_step_count(step_id=999)

    @pytest.mark.asyncio
    async def test_raises_on_non_int_total(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value={"meta": {"totalCount": "not-a-number"}}
        )

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api._resolved_user_id = "12345"
        with (
            patch.object(api, "_ensure_session", AsyncMock()),
            pytest.raises(DataParsingError, match="Unexpected WDK answer"),
        ):
            await api.get_step_count(step_id=999)


class TestStrategyAPICreateDataset:
    @pytest.mark.asyncio
    async def test_returns_dataset_id(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"id": 12345})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api._resolved_user_id = "12345"
        api._session_initialized = True
        config = WDKDatasetConfigIdList(
            source_type="idList",
            source_content=WDKDatasetIdListContent(ids=["GENE_A", "GENE_B"]),
        )
        result = await api.create_dataset(config)
        assert result == 12345

    @pytest.mark.asyncio
    async def test_raises_on_unexpected_response(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"error": "something wrong"})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api._resolved_user_id = "12345"
        api._session_initialized = True
        config = WDKDatasetConfigIdList(
            source_type="idList",
            source_content=WDKDatasetIdListContent(ids=["A"]),
        )
        with pytest.raises(pydantic.ValidationError):
            await api.create_dataset(config)


class TestRunPositiveNegativeControls:
    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_full_e2e_positive_and_negative(
        self, mock_get_api: MagicMock
    ) -> None:
        """Full flow with both positive and negative controls.

        Each control set creates its own target step, so create_step is
        called 4 times: target+controls for positive, target+controls for
        negative.
        """
        step_counter = 0

        async def _create_step(*args: Any, **kwargs: Any) -> WDKIdentifier:
            nonlocal step_counter
            step_counter += 1
            return WDKIdentifier(id=step_counter * 10)

        api = _make_mock_api(
            step_count=5,
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 2},
                "records": [
                    {"id": [{"name": "id", "value": "POS1"}]},
                    {"id": [{"name": "id", "value": "POS2"}]},
                ],
            },
        )
        api.create_step = AsyncMock(side_effect=_create_step)
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={"fold_change": "2"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        result = await run_positive_negative_controls(
            _cfg,
            positive_controls=["POS1", "POS2", "POS3"],
            negative_controls=["NEG1", "NEG2"],
        )

        # Target info comes from the positive run's target step
        assert result.target is not None
        assert result.target.step_id == 10  # first create_step call
        assert result.target.estimated_size == 5  # mocked step_count
        assert result.site_id == "plasmodb"

        # Positive results populated
        assert result.positive is not None
        assert result.positive.controls_count == 3
        assert result.positive.recall is not None

        # Negative results populated
        assert result.negative is not None
        assert result.negative.controls_count == 2

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_no_controls_returns_nulls(self, mock_get_api: MagicMock) -> None:
        """No positive or negative controls → null results, no steps created."""
        api = _make_mock_api()
        mock_get_api.return_value = api

        result = await run_positive_negative_controls(
            IntersectionConfig(
                site_id="plasmodb",
                record_type="transcript",
                target_search_name="GenesByRNASeq",
                target_parameters={},
                controls_search_name="GeneByLocusTag",
                controls_param_name="ds_gene_ids",
            ),
        )

        assert result.positive is None
        assert result.negative is None
        # No target step since no control sets were run
        assert result.target is not None
        assert result.target.step_id is None
        assert result.target.estimated_size is None

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_only_negative_fills_target_from_neg(
        self, mock_get_api: MagicMock
    ) -> None:
        """When only negative controls given, target info comes from neg run."""
        api = _make_mock_api(
            step_count=42,
            ids=_MockApiIds(
                create_combined_step_id=200,
                create_strategy_id=300,
                create_dataset_id=888,
            ),
            step_answer={
                "meta": {"totalCount": 1},
                "records": [
                    {"id": [{"name": "id", "value": "NEG1"}]},
                ],
            },
        )
        api.create_step = AsyncMock(
            side_effect=[WDKIdentifier(id=77), WDKIdentifier(id=78)]
        )
        mock_get_api.return_value = api

        _cfg = IntersectionConfig(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
        )
        result = await run_positive_negative_controls(
            _cfg,
            negative_controls=["NEG1", "NEG2"],
        )

        assert result.positive is None
        assert result.negative is not None
        # Target info filled from the negative run
        assert result.target is not None
        assert result.target.step_id == 77
        assert result.target.estimated_size == 42
