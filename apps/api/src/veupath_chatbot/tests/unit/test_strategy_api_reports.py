"""Unit tests for strategy API report, filter, analysis, and record mixins.

Tests FilterMixin, AnalysisMixin, ReportsMixin, and RecordsMixin covering:
filter operations, analysis lifecycle, report running, step answer/records
retrieval, column distribution, and step count.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api.analyses import (
    AnalysisMixin,
    AnalysisPollConfig,
)
from veupath_chatbot.integrations.veupathdb.strategy_api.filters import FilterMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.records import RecordsMixin
from veupath_chatbot.integrations.veupathdb.strategy_api.reports import ReportsMixin
from veupath_chatbot.platform.errors import DataParsingError, InternalError, WDKError


def _make_client() -> MagicMock:
    """Create a mock VEuPathDB client with all needed async methods."""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.patch = AsyncMock()
    client.delete = AsyncMock()
    client.get_step_view_filters = AsyncMock(return_value=[])
    client.update_step_view_filters = AsyncMock(return_value={})
    client.list_analysis_types = AsyncMock(return_value=[])
    client.get_analysis_type = AsyncMock(return_value={})
    client.list_step_analyses = AsyncMock(return_value=[])
    client.create_step_analysis = AsyncMock()
    client.run_analysis_instance = AsyncMock()
    client.get_analysis_status = AsyncMock()
    client.get_analysis_result = AsyncMock()
    client.run_step_report = AsyncMock()
    return client


def _make_filter_mixin(user_id: str = "12345") -> tuple[FilterMixin, MagicMock]:
    """Create a FilterMixin with a mock client, pre-initialized session."""
    client = _make_client()
    mixin = FilterMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


def _make_analysis_mixin(user_id: str = "12345") -> tuple[AnalysisMixin, MagicMock]:
    """Create an AnalysisMixin with a mock client, pre-initialized session."""
    client = _make_client()
    mixin = AnalysisMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


def _make_reports_mixin(user_id: str = "12345") -> tuple[ReportsMixin, MagicMock]:
    """Create a ReportsMixin with a mock client, pre-initialized session."""
    client = _make_client()
    mixin = ReportsMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


def _make_records_mixin(user_id: str = "12345") -> tuple[RecordsMixin, MagicMock]:
    """Create a RecordsMixin with a mock client, pre-initialized session."""
    client = _make_client()
    mixin = RecordsMixin(client, user_id=user_id)
    mixin._session_initialized = True
    return mixin, client


# ---------------------------------------------------------------------------
# Filter operations
# ---------------------------------------------------------------------------


class TestFilterOperations:
    """Step filter CRUD."""

    async def test_set_step_filter(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = []
        await mixin.set_step_filter(
            step_id=42,
            filter_name="matched_transcript_filter_array",
            value={"values": ["yes"]},
        )
        client.update_step_view_filters.assert_awaited_once()
        filters = client.update_step_view_filters.call_args.args[2]
        assert len(filters) == 1
        assert filters[0]["name"] == "matched_transcript_filter_array"
        assert filters[0]["value"] == {"values": ["yes"]}
        assert filters[0]["disabled"] is False

    async def test_set_step_filter_disabled(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = []
        await mixin.set_step_filter(
            step_id=42, filter_name="f", value={}, disabled=True
        )
        filters = client.update_step_view_filters.call_args.args[2]
        assert filters[0]["disabled"] is True

    async def test_delete_step_filter(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = [
            {"name": "my_filter", "value": 1, "disabled": False},
        ]
        await mixin.delete_step_filter(step_id=42, filter_name="my_filter")
        client.update_step_view_filters.assert_awaited_once()
        filters = client.update_step_view_filters.call_args.args[2]
        assert filters == []

    async def test_list_step_filters(self) -> None:
        mixin, client = _make_filter_mixin()
        client.get_step_view_filters.return_value = [{"name": "f1"}]
        result = await mixin.list_step_filters(step_id=42)
        assert result == [{"name": "f1"}]

    async def test_list_analysis_types(self) -> None:
        mixin, client = _make_analysis_mixin()
        client.list_analysis_types.return_value = [{"name": "go-enrichment"}]
        result = await mixin.list_analysis_types(step_id=42)
        assert result == [{"name": "go-enrichment"}]

    async def test_get_analysis_type(self) -> None:
        mixin, client = _make_analysis_mixin()
        client.get_analysis_type.return_value = {"searchData": {"parameters": []}}
        result = await mixin.get_analysis_type(
            step_id=42, analysis_type="go-enrichment"
        )
        assert "searchData" in result


# ---------------------------------------------------------------------------
# run_step_report
# ---------------------------------------------------------------------------


class TestRunStepReport:
    """Step report execution."""

    async def test_run_step_report_basic(self) -> None:
        mixin, client = _make_reports_mixin()
        client.run_step_report.return_value = {"records": []}
        await mixin.run_step_report(step_id=42, report_name="standard")
        client.run_step_report.assert_awaited_once_with(
            "12345", 42, "standard", {"reportConfig": {}}
        )

    async def test_run_step_report_with_config(self) -> None:
        mixin, client = _make_reports_mixin()
        client.run_step_report.return_value = {"records": []}
        config = {"pagination": {"offset": 0, "numRecords": 10}}
        await mixin.run_step_report(step_id=42, report_name="standard", config=config)
        call_payload = client.run_step_report.call_args.args[3]
        assert call_payload["reportConfig"] == config


# ---------------------------------------------------------------------------
# get_step_answer
# ---------------------------------------------------------------------------


class TestGetStepAnswer:
    """Step answer retrieval via standard report endpoint."""

    async def test_basic_answer(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {
            "records": [{"id": [{"name": "source_id", "value": "PF3D7_0100100"}]}],
            "meta": {"totalCount": 1},
        }
        result = await mixin.get_step_answer(step_id=42)
        assert "records" in result

    async def test_answer_with_attributes(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"records": [], "meta": {"totalCount": 0}}
        await mixin.get_step_answer(step_id=42, attributes=["gene_name", "product"])
        payload = client.post.call_args.kwargs["json"]
        assert payload["reportConfig"]["attributes"] == ["gene_name", "product"]

    async def test_answer_with_pagination(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"records": [], "meta": {"totalCount": 0}}
        await mixin.get_step_answer(
            step_id=42, pagination={"offset": 0, "numRecords": 10}
        )
        payload = client.post.call_args.kwargs["json"]
        assert payload["reportConfig"]["pagination"] == {"offset": 0, "numRecords": 10}


# ---------------------------------------------------------------------------
# get_step_records
# ---------------------------------------------------------------------------


class TestGetStepRecords:
    """Step records retrieval with configurable options."""

    async def test_with_all_options(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"records": [], "meta": {"totalCount": 0}}

        await mixin.get_step_records(
            step_id=42,
            attributes=["gene_name"],
            tables=["GoTerms"],
            pagination={"offset": 0, "numRecords": 5},
            sorting=[{"attributeName": "gene_name", "direction": "ASC"}],
        )

        payload = client.post.call_args.kwargs["json"]
        config = payload["reportConfig"]
        assert config["attributes"] == ["gene_name"]
        assert config["tables"] == ["GoTerms"]
        assert config["pagination"] == {"offset": 0, "numRecords": 5}
        assert config["sorting"] == [{"attributeName": "gene_name", "direction": "ASC"}]

    async def test_minimal_options(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"records": [], "meta": {"totalCount": 0}}
        await mixin.get_step_records(step_id=42)
        payload = client.post.call_args.kwargs["json"]
        assert payload["reportConfig"] == {}


# ---------------------------------------------------------------------------
# get_record_type_info
# ---------------------------------------------------------------------------


class TestGetRecordTypeInfo:
    """Record type metadata retrieval."""

    async def test_fetches_expanded_record_type(self) -> None:
        mixin, client = _make_records_mixin()
        client.get.return_value = {"urlSegment": "gene", "attributes": []}
        await mixin.get_record_type_info("gene")
        client.get.assert_awaited_once_with(
            "/record-types/gene",
            params={"format": "expanded"},
        )


# ---------------------------------------------------------------------------
# get_single_record
# ---------------------------------------------------------------------------


class TestGetSingleRecord:
    """Single record retrieval by primary key."""

    async def test_basic_fetch(self) -> None:
        mixin, client = _make_records_mixin()
        client.post.return_value = {
            "id": [{"name": "source_id", "value": "PF3D7_0100100"}]
        }
        pk = [{"name": "source_id", "value": "PF3D7_0100100"}]
        await mixin.get_single_record("gene", pk)
        payload = client.post.call_args.kwargs["json"]
        assert payload["primaryKey"] == pk
        assert payload["attributes"] == []
        assert payload["tables"] == []

    async def test_with_attributes_and_tables(self) -> None:
        mixin, client = _make_records_mixin()
        client.post.return_value = {}
        pk = [{"name": "source_id", "value": "PF3D7_0100100"}]
        await mixin.get_single_record(
            "gene", pk, attributes=["gene_name"], tables=["GoTerms"]
        )
        payload = client.post.call_args.kwargs["json"]
        assert payload["attributes"] == ["gene_name"]
        assert payload["tables"] == ["GoTerms"]


# ---------------------------------------------------------------------------
# get_column_distribution
# ---------------------------------------------------------------------------


class TestGetColumnDistribution:
    """Column distribution via the byValue reporter."""

    async def test_returns_distribution(self) -> None:
        mixin, client = _make_records_mixin()
        client.post.return_value = {
            "histogram": [{"value": "A", "count": 10}],
            "statistics": {},
        }
        result = await mixin.get_column_distribution(step_id=42, column_name="organism")
        assert "histogram" in result

    async def test_returns_empty_on_wdk_error(self) -> None:
        """Not all columns support the byValue reporter."""
        mixin, client = _make_records_mixin()
        client.post.side_effect = WDKError("column reporter unavailable", status=400)
        result = await mixin.get_column_distribution(step_id=42, column_name="overview")
        assert result == {"histogram": [], "statistics": {}}


# ---------------------------------------------------------------------------
# get_step_count
# ---------------------------------------------------------------------------


class TestGetStepCount:
    """Step count extraction from standard report meta.totalCount."""

    async def test_returns_total_count(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {
            "records": [],
            "meta": {"totalCount": 42},
        }
        count = await mixin.get_step_count(step_id=1)
        assert count == 42

    async def test_zero_count(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {
            "records": [],
            "meta": {"totalCount": 0},
        }
        count = await mixin.get_step_count(step_id=1)
        assert count == 0

    async def test_raises_on_non_dict_response(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = []  # wrong type -- normalized to {} by _standard_report
        with pytest.raises(DataParsingError, match="missing 'meta'"):
            await mixin.get_step_count(step_id=1)

    async def test_raises_on_missing_meta(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"records": []}
        with pytest.raises(DataParsingError, match="missing 'meta'"):
            await mixin.get_step_count(step_id=1)

    async def test_raises_on_non_int_total_count(self) -> None:
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"meta": {"totalCount": "42"}}
        with pytest.raises(DataParsingError, match="not an int"):
            await mixin.get_step_count(step_id=1)

    async def test_step_count_request_uses_zero_records(self) -> None:
        """Step count should request 0 records to minimize transfer."""
        mixin, client = _make_reports_mixin()
        client.post.return_value = {"records": [], "meta": {"totalCount": 0}}
        await mixin.get_step_count(step_id=1)
        payload = client.post.call_args.kwargs["json"]
        assert payload["reportConfig"]["pagination"]["numRecords"] == 0


# ---------------------------------------------------------------------------
# run_step_analysis
# ---------------------------------------------------------------------------


class TestRunStepAnalysis:
    """Multi-phase step analysis lifecycle."""

    async def test_successful_analysis(self) -> None:
        mixin, client = _make_analysis_mixin()
        # Phase 0: warmup
        client.post.side_effect = [
            # warmup report
            {"meta": {"totalCount": 100}},
            # Phase 1: create analysis
            None,  # will be overridden
        ]
        client.create_step_analysis.return_value = {"analysisId": 7}
        client.run_analysis_instance.return_value = {"status": "RUNNING"}
        client.get_analysis_status.return_value = {"status": "COMPLETE"}
        client.get_analysis_result.return_value = {
            "rows": [{"term": "GO:0001", "pvalue": 0.01}]
        }

        # Override post to handle warmup
        warmup_call_count = 0
        original_post = client.post

        async def smart_post(path: str, json: object = None) -> object:
            nonlocal warmup_call_count
            if "reports/standard" in path:
                warmup_call_count += 1
                return {"meta": {"totalCount": 100}}
            return await original_post(path, json=json)

        client.post = AsyncMock(side_effect=smart_post)

        result = await mixin.run_step_analysis(
            step_id=42,
            analysis_type="go-enrichment",
            parameters={"organism": "Plasmodium falciparum 3D7"},
            poll_config=AnalysisPollConfig(poll_interval=0.01),
        )

        rows = result["rows"]
        assert isinstance(rows, list)
        first_row = rows[0]
        assert isinstance(first_row, dict)
        assert first_row["term"] == "GO:0001"
        client.create_step_analysis.assert_awaited_once()
        client.run_analysis_instance.assert_awaited_once_with("12345", 42, 7)

    async def test_raises_on_missing_analysis_id(self) -> None:
        mixin, client = _make_analysis_mixin()
        client.post.return_value = {"meta": {"totalCount": 100}}
        client.create_step_analysis.return_value = {"no_id": True}

        with pytest.raises(InternalError, match="creation failed"):
            await mixin.run_step_analysis(
                step_id=42,
                analysis_type="go-enrichment",
                poll_config=AnalysisPollConfig(poll_interval=0.01),
            )

    async def test_raises_on_expired_status(self) -> None:
        mixin, client = _make_analysis_mixin()
        client.post.return_value = {"meta": {"totalCount": 100}}
        client.create_step_analysis.return_value = {"analysisId": 7}
        client.run_analysis_instance.return_value = {}
        client.get_analysis_status.return_value = {"status": "EXPIRED"}

        with pytest.raises(InternalError, match="analysis failed"):
            await mixin.run_step_analysis(
                step_id=42,
                analysis_type="go-enrichment",
                poll_config=AnalysisPollConfig(poll_interval=0.01),
            )

    async def test_retries_on_error_status(self) -> None:
        """ERROR status triggers re-run of the same analysis instance."""
        mixin, client = _make_analysis_mixin()
        client.post.return_value = {"meta": {"totalCount": 100}}
        client.create_step_analysis.return_value = {"analysisId": 7}
        client.run_analysis_instance.return_value = {}
        # First poll: ERROR, second poll after re-run: COMPLETE
        client.get_analysis_status.side_effect = [
            {"status": "ERROR"},
            {"status": "COMPLETE"},
        ]
        client.get_analysis_result.return_value = {"rows": []}

        result = await mixin.run_step_analysis(
            step_id=42,
            analysis_type="go-enrichment",
            poll_config=AnalysisPollConfig(poll_interval=0.01),
        )
        assert result == {"rows": []}
        # run_analysis_instance called twice: initial + retry
        assert client.run_analysis_instance.call_count == 2
