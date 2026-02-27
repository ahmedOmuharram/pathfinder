"""Tests for veupath_chatbot.services.control_tests.

All WDK calls are mocked. These tests validate:
- get_step_answer uses POST /reports/standard (not GET /answer)
- get_step_count uses POST /reports/standard
- _get_total_count_for_step wraps get_step_count correctly
- _run_intersection_control wires steps, creates strategy, fetches answer
- resolve_controls_param_type correctly detects input-dataset params
- _extract_record_ids extracts IDs from WDK answer records
- _encode_id_list formats correctly
- run_positive_negative_controls composes results
- dataset creation path for input-dataset params
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.control_tests import (
    _encode_id_list,
    _extract_record_ids,
    _get_total_count_for_step,
    _run_intersection_control,
    resolve_controls_param_type,
    run_positive_negative_controls,
)


def _make_mock_api(
    *,
    step_count: int = 42,
    step_answer: JSONObject | None = None,
    create_step_id: int = 100,
    create_combined_step_id: int = 200,
    create_strategy_id: int = 300,
    create_dataset_id: int = 999,
    search_details: JSONObject | None = None,
) -> AsyncMock:
    """Build an AsyncMock that behaves like StrategyAPI.

    :param step_count: Number of mock steps (default: 42).
    :param step_answer: Mock step answer payload (default: None).
    :param create_step_id: Mock create_step ID (default: 100).
    :param create_combined_step_id: Mock create_combined_step ID (default: 200).
    :param create_strategy_id: Mock create_strategy ID (default: 300).
    :param create_dataset_id: Mock create_dataset ID (default: 999).
    :param search_details: Mock search details (default: None).

    """
    api = AsyncMock(spec=StrategyAPI)

    # get_step_count returns an int
    api.get_step_count = AsyncMock(return_value=step_count)

    # get_step_answer returns dict with meta + records
    default_answer = step_answer or {
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
    api.get_step_answer = AsyncMock(return_value=default_answer)

    # create_step returns {"id": <step_id>}
    api.create_step = AsyncMock(return_value={"id": create_step_id})

    # create_combined_step returns {"id": <combined_step_id>}
    api.create_combined_step = AsyncMock(return_value={"id": create_combined_step_id})

    # create_strategy returns {"id": <strategy_id>}
    api.create_strategy = AsyncMock(return_value={"id": create_strategy_id})

    # delete_strategy succeeds
    api.delete_strategy = AsyncMock(return_value=None)
    api.list_strategies = AsyncMock(return_value=[])

    # create_dataset returns dataset ID
    api.create_dataset = AsyncMock(return_value=create_dataset_id)

    # client.get_search_details returns search details
    api.client = MagicMock()
    api.client.get_search_details = AsyncMock(
        return_value=search_details
        or {
            "searchData": {
                "parameters": [
                    {"name": "ds_gene_ids", "type": "input-dataset"},
                    {"name": "other_param", "type": "string"},
                ]
            }
        }
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
        import json

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
        records: JSONArray = [
            {"id": [{"name": "source_id", "value": "GENE1"}]},
            {"id": [{"name": "source_id", "value": "GENE2"}]},
        ]
        assert _extract_record_ids(records) == ["GENE1", "GENE2"]

    def test_extracts_from_preferred_key(self) -> None:
        records: JSONArray = [
            cast(
                JSONObject,
                {
                    "id": [{"name": "source_id", "value": "PK1"}],
                    "attributes": {"gene_id": "ATTR1"},
                },
            ),
        ]
        assert _extract_record_ids(records, preferred_key="gene_id") == ["ATTR1"]

    def test_falls_back_to_id_when_preferred_missing(self) -> None:
        records: JSONArray = [
            {
                "id": [{"name": "source_id", "value": "PK1"}],
                "attributes": {"other": "X"},
            },
        ]
        assert _extract_record_ids(records, preferred_key="gene_id") == ["PK1"]

    def test_returns_empty_for_non_list(self) -> None:
        assert _extract_record_ids(None) == []
        assert _extract_record_ids("not a list") == []

    def test_skips_malformed_records(self) -> None:
        records: JSONArray = [
            None,
            "bad",
            {"id": []},
            {"id": [{"name": "source_id", "value": "GOOD"}]},
        ]
        assert _extract_record_ids(records) == ["GOOD"]

    def test_composite_primary_key_extracts_first(self) -> None:
        """For composite keys (e.g., transcript), first PK value is extracted."""
        records: JSONArray = [
            {
                "id": [
                    {"name": "source_id", "value": "PF3D7_0209000"},
                    {"name": "project_id", "value": "PlasmoDB"},
                ],
            },
        ]
        assert _extract_record_ids(records) == ["PF3D7_0209000"]


class TestGetTotalCountForStep:
    @pytest.mark.asyncio
    async def test_returns_count_on_success(self) -> None:
        api = _make_mock_api(step_count=123)
        result = await _get_total_count_for_step(api, 42)
        assert result == 123
        api.get_step_count.assert_awaited_once_with(42)

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self) -> None:
        api = _make_mock_api()
        api.get_step_count = AsyncMock(side_effect=Exception("WDK error"))
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
            side_effect=Exception("network error")
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
        target_step_resp = {"id": 50}
        controls_step_resp = {"id": 51}
        api = _make_mock_api(
            step_count=3,
            create_combined_step_id=60,
            create_strategy_id=70,
            create_dataset_id=12345,
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
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={"fold_change": "2"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_ids=["PF3D7_001", "PF3D7_002", "PF3D7_003"],
            controls_value_format="newline",
            controls_extra_parameters=None,
        )

        # Dataset was created
        api.create_dataset.assert_awaited_once_with(
            ["PF3D7_001", "PF3D7_002", "PF3D7_003"]
        )

        # create_step called twice: target + controls
        assert api.create_step.await_count == 2
        # Second call (controls) should have dataset ID
        controls_call_kwargs = api.create_step.call_args_list[1][1]
        assert controls_call_kwargs["parameters"]["ds_gene_ids"] == "12345"

        # Combined step and strategy were created
        api.create_combined_step.assert_awaited_once()
        api.create_strategy.assert_awaited_once()

        # get_step_count called twice: target step + combined step
        assert api.get_step_count.await_count == 2

        # get_step_answer was called for records
        api.get_step_answer.assert_awaited_once_with(
            60,
            pagination={"offset": 0, "numRecords": 3},
        )

        # Strategy was cleaned up
        api.delete_strategy.assert_awaited_once_with(70)

        # Result shape
        assert result["controlsCount"] == 3
        assert result["intersectionCount"] == 3
        assert result["targetStepId"] == 50
        assert result["targetResultCount"] == 3
        assert result["intersectionIds"] == [
            "PF3D7_001",
            "PF3D7_002",
            "PF3D7_003",
        ]

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_flow_with_newline_format(self, mock_get_api: MagicMock) -> None:
        """When param is NOT input-dataset, encode IDs directly."""
        api = _make_mock_api(
            search_details={
                "searchData": {
                    "parameters": [
                        {"name": "gene_list", "type": "string"},
                    ]
                }
            },
        )
        # Two create_step calls: target + controls
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        mock_get_api.return_value = api

        await _run_intersection_control(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="SomeRNASearch",
            target_parameters={"fold": "1"},
            controls_search_name="SomeSearch",
            controls_param_name="gene_list",
            controls_ids=["A", "B", "C"],
            controls_value_format="newline",
            controls_extra_parameters=None,
        )

        # No dataset created
        api.create_dataset.assert_not_awaited()

        # Second create_step call (controls) has newline-encoded IDs
        controls_call_kwargs = api.create_step.call_args_list[1][1]
        assert controls_call_kwargs["parameters"]["gene_list"] == "A\nB\nC"

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_cleanup_on_answer_failure(self, mock_get_api: MagicMock) -> None:
        """Strategy is cleaned up even if get_step_answer fails."""
        api = _make_mock_api()
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        api.get_step_answer = AsyncMock(side_effect=Exception("WDK boom"))
        mock_get_api.return_value = api

        with pytest.raises(Exception, match="WDK boom"):
            await _run_intersection_control(
                site_id="plasmodb",
                record_type="transcript",
                target_search_name="GenesByRNASeq",
                target_parameters={},
                controls_search_name="GeneByLocusTag",
                controls_param_name="ds_gene_ids",
                controls_ids=["A"],
                controls_value_format="newline",
                controls_extra_parameters=None,
            )

        # Strategy was still cleaned up
        api.delete_strategy.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_cleans_up_stale_internal_control_test_strategies(
        self, mock_get_api: MagicMock
    ) -> None:
        api = _make_mock_api(
            search_details={
                "searchData": {
                    "parameters": [
                        {"name": "gene_list", "type": "string"},
                    ]
                }
            }
        )
        api.create_step = AsyncMock(side_effect=[{"id": 10}, {"id": 11}])
        api.list_strategies = AsyncMock(
            return_value=[
                {
                    "strategyId": 123,
                    "name": "__pathfinder_internal__:Pathfinder control test",
                },
                {
                    "strategyId": 456,
                    "name": "__pathfinder_internal__:Other internal helper",
                },
                {"strategyId": 789, "name": "User visible strategy"},
            ]
        )
        mock_get_api.return_value = api

        await _run_intersection_control(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="SomeRNASearch",
            target_parameters={"fold": "1"},
            controls_search_name="SomeSearch",
            controls_param_name="gene_list",
            controls_ids=["A", "B"],
            controls_value_format="newline",
            controls_extra_parameters=None,
        )

        # One stale internal control-test strategy + the newly created temp strategy.
        assert api.delete_strategy.await_count == 2
        deleted_ids = [c.args[0] for c in api.delete_strategy.await_args_list]
        assert 123 in deleted_ids

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_each_call_creates_own_target_step(
        self, mock_get_api: MagicMock
    ) -> None:
        """Verify each call creates its own target step (no sharing)."""
        call_count = 0

        async def _create_step_side_effect(**kwargs: Any) -> JSONObject:
            nonlocal call_count
            call_count += 1
            return {"id": call_count * 10}

        api = _make_mock_api()
        api.create_step = AsyncMock(side_effect=_create_step_side_effect)
        mock_get_api.return_value = api

        # First call
        r1 = await _run_intersection_control(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={"fold_change": "2"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_ids=["POS1"],
            controls_value_format="newline",
            controls_extra_parameters=None,
        )
        assert r1["targetStepId"] == 10  # first create_step call

        # Second call (simulating negative controls after positive)
        r2 = await _run_intersection_control(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={"fold_change": "2"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            controls_ids=["NEG1"],
            controls_value_format="newline",
            controls_extra_parameters=None,
        )
        assert r2["targetStepId"] == 30  # third create_step call (new target)
        # Total: 4 create_step calls (target+controls for each run)
        assert api.create_step.await_count == 4


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
        api.user_id = "12345"
        api._session_initialized = True  # bypass _ensure_session

        result = await api.get_step_answer(
            step_id=999,
            pagination={"offset": 0, "numRecords": 10},
        )

        # Verify POST was called (not GET)
        mock_client.post.assert_awaited_once_with(
            "/users/12345/steps/999/reports/standard",
            json={"reportConfig": {"pagination": {"offset": 0, "numRecords": 10}}},
        )
        assert result == {"meta": {"totalCount": 5}, "records": []}

    @pytest.mark.asyncio
    async def test_with_attributes(self) -> None:
        """Attributes are passed in reportConfig."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"meta": {}, "records": []})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api.user_id = "12345"
        with patch.object(api, "_ensure_session", AsyncMock()):
            await api.get_step_answer(
                step_id=999,
                attributes=["source_id", "gene_name"],
                pagination={"offset": 0, "numRecords": 5},
            )

        mock_client.post.assert_awaited_once_with(
            "/users/12345/steps/999/reports/standard",
            json={
                "reportConfig": {
                    "attributes": ["source_id", "gene_name"],
                    "pagination": {"offset": 0, "numRecords": 5},
                }
            },
        )

    @pytest.mark.asyncio
    async def test_empty_report_config(self) -> None:
        """No attributes or pagination → empty reportConfig."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"meta": {}, "records": []})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api.user_id = "12345"
        with patch.object(api, "_ensure_session", AsyncMock()):
            await api.get_step_answer(step_id=999)

        mock_client.post.assert_awaited_once_with(
            "/users/12345/steps/999/reports/standard",
            json={"reportConfig": {}},
        )


class TestStrategyAPIGetStepCount:
    @pytest.mark.asyncio
    async def test_returns_total_count(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value={"meta": {"totalCount": 42}, "records": []}
        )

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api.user_id = "12345"
        with patch.object(api, "_ensure_session", AsyncMock()):
            result = await api.get_step_count(step_id=999)
        assert result == 42

        mock_client.post.assert_awaited_once_with(
            "/users/12345/steps/999/reports/standard",
            json={"reportConfig": {"pagination": {"offset": 0, "numRecords": 0}}},
        )

    @pytest.mark.asyncio
    async def test_raises_on_missing_meta(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"records": []})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api.user_id = "12345"
        with (
            patch.object(api, "_ensure_session", AsyncMock()),
            pytest.raises(ValueError, match="missing 'meta'"),
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
        api.user_id = "12345"
        with (
            patch.object(api, "_ensure_session", AsyncMock()),
            pytest.raises(ValueError, match="not an int"),
        ):
            await api.get_step_count(step_id=999)


class TestStrategyAPICreateDataset:
    @pytest.mark.asyncio
    async def test_returns_dataset_id(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"id": 12345})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api.user_id = "12345"
        with patch.object(api, "_ensure_session", AsyncMock()):
            result = await api.create_dataset(["GENE_A", "GENE_B"])
        assert result == 12345

        mock_client.post.assert_awaited_once_with(
            "/users/12345/datasets",
            json={
                "sourceType": "idList",
                "sourceContent": {"ids": ["GENE_A", "GENE_B"]},
            },
        )

    @pytest.mark.asyncio
    async def test_raises_on_unexpected_response(self) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value={"error": "something wrong"})

        api = StrategyAPI.__new__(StrategyAPI)
        api.client = mock_client
        api.user_id = "12345"
        with (
            patch.object(api, "_ensure_session", AsyncMock()),
            pytest.raises(Exception, match="Dataset creation failed"),
        ):
            await api.create_dataset(["A"])


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

        async def _create_step(**kwargs: Any) -> JSONObject:
            nonlocal step_counter
            step_counter += 1
            return {"id": step_counter * 10}

        api = _make_mock_api(
            step_count=5,
            create_combined_step_id=200,
            create_strategy_id=300,
            create_dataset_id=888,
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

        result = await run_positive_negative_controls(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={"fold_change": "2"},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            positive_controls=["POS1", "POS2", "POS3"],
            negative_controls=["NEG1", "NEG2"],
            controls_value_format="newline",
        )

        # Target info comes from the positive run's target step
        target = result.get("target")
        assert isinstance(target, dict)
        assert target["stepId"] == 10  # first create_step call
        assert target["resultCount"] == 5  # mocked step_count
        assert result["siteId"] == "plasmodb"

        # Positive results populated
        positive = result.get("positive")
        assert positive is not None and isinstance(positive, dict)
        assert positive["controlsCount"] == 3
        assert positive["recall"] is not None

        # Negative results populated
        negative = result.get("negative")
        assert negative is not None and isinstance(negative, dict)
        assert negative["controlsCount"] == 2

        # 4 create_step calls total (2 per control set)
        assert api.create_step.await_count == 4

        # 2 strategies created (one per control set) and cleaned up
        assert api.create_strategy.await_count == 2
        assert api.delete_strategy.await_count == 2

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_no_controls_returns_nulls(self, mock_get_api: MagicMock) -> None:
        """No positive or negative controls → null results, no steps created."""
        api = _make_mock_api()
        mock_get_api.return_value = api

        result = await run_positive_negative_controls(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
        )

        assert result["positive"] is None
        assert result["negative"] is None
        # No target step since no control sets were run
        target = result.get("target")
        assert isinstance(target, dict)
        assert target["stepId"] is None
        assert target["resultCount"] is None
        # No WDK calls made
        api.create_step.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("veupath_chatbot.services.control_tests.get_strategy_api")
    async def test_only_negative_fills_target_from_neg(
        self, mock_get_api: MagicMock
    ) -> None:
        """When only negative controls given, target info comes from neg run."""
        api = _make_mock_api(
            step_count=42,
            create_combined_step_id=200,
            create_strategy_id=300,
            create_dataset_id=888,
            step_answer={
                "meta": {"totalCount": 1},
                "records": [
                    {"id": [{"name": "id", "value": "NEG1"}]},
                ],
            },
        )
        api.create_step = AsyncMock(side_effect=[{"id": 77}, {"id": 78}])
        mock_get_api.return_value = api

        result = await run_positive_negative_controls(
            site_id="plasmodb",
            record_type="transcript",
            target_search_name="GenesByRNASeq",
            target_parameters={},
            controls_search_name="GeneByLocusTag",
            controls_param_name="ds_gene_ids",
            negative_controls=["NEG1", "NEG2"],
        )

        assert result["positive"] is None
        assert result["negative"] is not None
        # Target info filled from the negative run
        target = result.get("target")
        assert isinstance(target, dict)
        assert target["stepId"] == 77
        assert target["resultCount"] == 42
