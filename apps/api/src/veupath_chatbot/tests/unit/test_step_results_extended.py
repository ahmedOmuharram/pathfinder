"""Extended tests for WDK step results service and enrichment service.

Covers: attribute listing edge cases, record browsing with empty/large results,
distribution fallback, analysis type discovery, record detail PK ordering,
and enrichment edge cases.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKColumnDistribution,
    WDKHistogramBin,
    WDKHistogramStatistics,
    WDKRecordInstance,
    WDKRecordType,
    WDKStepAnalysisType,
)
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.wdk.helpers import (
    build_attribute_list,
    extract_pk,
    extract_record_ids,
    merge_analysis_params,
    order_primary_key,
)
from veupath_chatbot.services.wdk.step_results import StepResultsService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api() -> MagicMock:
    """Create a mock StrategyAPI."""
    api = MagicMock()
    api.get_record_type_info = AsyncMock()
    api.get_step_records = AsyncMock()
    api.get_column_distribution = AsyncMock()
    api.list_analysis_types = AsyncMock()
    api.get_strategy = AsyncMock()
    api.get_analysis_type = AsyncMock()
    api.run_step_analysis = AsyncMock()
    api.get_single_record = AsyncMock()
    api._ensure_session = AsyncMock()
    return api


def _make_service(
    step_id: int = 42,
    record_type: str = "gene",
) -> tuple[StepResultsService, MagicMock]:
    """Create a StepResultsService with a mock API."""
    api = _make_api()
    svc = StepResultsService(api, step_id=step_id, record_type=record_type)
    return svc, api


# ===========================================================================
# StepResultsService -get_attributes
# ===========================================================================


class TestGetAttributes:
    """Attribute listing from record type info."""

    async def test_returns_attributes_from_attributes_key(self) -> None:
        """Standard WDK response has 'attributes' as a list."""
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate({
            "urlSegment": "gene",
            "attributes": [
                {"name": "gene_name", "displayName": "Gene Name", "type": "string"},
            ],
        })
        result = await svc.get_attributes()
        assert result["recordType"] == "gene"
        assert len(result["attributes"]) == 1
        assert result["attributes"][0]["name"] == "gene_name"

    async def test_falls_back_to_attributes_map(self) -> None:
        """Some WDK deployments use 'attributesMap' dict format."""
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate({
            "urlSegment": "gene",
            "attributesMap": {
                "gene_name": {"displayName": "Gene Name", "type": "string"},
            },
        })
        result = await svc.get_attributes()
        assert len(result["attributes"]) == 1

    async def test_empty_attributes(self) -> None:
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate({
            "urlSegment": "gene",
            "attributes": [],
        })
        result = await svc.get_attributes()
        assert result["attributes"] == []

    async def test_no_attributes_key(self) -> None:
        """If neither 'attributes' nor 'attributesMap' exists, return empty."""
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate({
            "urlSegment": "gene",
        })
        result = await svc.get_attributes()
        assert result["attributes"] == []


# ===========================================================================
# StepResultsService -get_records
# ===========================================================================


class TestGetRecords:
    """Record browsing edge cases."""

    async def test_default_pagination(self) -> None:
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "records": [],
            "meta": {"totalCount": 0},
        })
        result = await svc.get_records()
        call_kwargs = api.get_step_records.call_args.kwargs
        assert call_kwargs["pagination"] == {"offset": 0, "numRecords": 50}
        assert result["records"] == []

    async def test_custom_pagination(self) -> None:
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "records": [{"id": [{"name": "source_id", "value": "X"}]}],
            "meta": {"totalCount": 1},
        })
        await svc.get_records(offset=10, limit=5)
        call_kwargs = api.get_step_records.call_args.kwargs
        assert call_kwargs["pagination"] == {"offset": 10, "numRecords": 5}

    async def test_sorting_applied(self) -> None:
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "records": [],
            "meta": {"totalCount": 0},
        })
        await svc.get_records(sort="gene_name", direction="DESC")
        call_kwargs = api.get_step_records.call_args.kwargs
        assert call_kwargs["sorting"] == [
            {"attributeName": "gene_name", "direction": "DESC"}
        ]

    async def test_no_sorting_when_sort_is_none(self) -> None:
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "records": [],
            "meta": {"totalCount": 0},
        })
        await svc.get_records()
        call_kwargs = api.get_step_records.call_args.kwargs
        assert call_kwargs["sorting"] is None

    async def test_direction_uppercased(self) -> None:
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "records": [],
            "meta": {"totalCount": 0},
        })
        await svc.get_records(sort="col", direction="asc")
        call_kwargs = api.get_step_records.call_args.kwargs
        assert call_kwargs["sorting"][0]["direction"] == "ASC"

    async def test_missing_records_key_defaults_empty(self) -> None:
        """WDKAnswer defaults 'records' to empty list when omitted."""
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "meta": {"totalCount": 0},
        })
        result = await svc.get_records()
        assert result["records"] == []

    async def test_empty_meta_defaults(self) -> None:
        """WDKAnswerMeta defaults all fields when meta dict is empty."""
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate({
            "records": [],
            "meta": {},
        })
        result = await svc.get_records()
        assert result["meta"]["totalCount"] == 0


# ===========================================================================
# StepResultsService -get_distribution
# ===========================================================================


class TestGetDistribution:
    """Distribution data retrieval."""

    async def test_delegates_to_api(self) -> None:
        svc, api = _make_service()
        api.get_column_distribution.return_value = WDKColumnDistribution(
            histogram=[WDKHistogramBin(value=10, bin_label="A")],
            statistics=WDKHistogramStatistics(subset_size=100),
        )
        result = await svc.get_distribution("organism")
        api.get_column_distribution.assert_awaited_once_with(42, "organism")
        assert isinstance(result, WDKColumnDistribution)
        assert len(result.histogram) == 1


# ===========================================================================
# StepResultsService -list_analysis_types
# ===========================================================================


class TestListAnalysisTypes:
    async def test_wraps_result(self) -> None:
        svc, api = _make_service()
        api.list_analysis_types.return_value = [
            WDKStepAnalysisType(name="go-enrichment", display_name="GO Enrichment"),
            WDKStepAnalysisType(name="pathway-enrichment", display_name="Pathway Enrichment"),
        ]
        result = await svc.list_analysis_types()
        assert len(result["analysisTypes"]) == 2


# ===========================================================================
# StepResultsService -get_record_detail
# ===========================================================================


class TestGetRecordDetail:
    """Record detail retrieval with PK reordering."""

    async def test_reorders_pk_parts(self) -> None:
        """PK parts should be reordered to match WDK record class definition."""
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate({
            "urlSegment": "gene",
            "primaryKeyColumnRefs": ["source_id", "project_id"],
        })
        api.get_single_record.return_value = WDKRecordInstance.model_validate({
            "id": [{"name": "source_id", "value": "PF3D7_0100100"}],
            "attributes": {},
        })
        with patch(
            "veupath_chatbot.integrations.veupathdb.factory.get_site",
            return_value=MagicMock(project_id="PlasmoDB"),
        ):
            await svc.get_record_detail(
                primary_key=[
                    {"name": "project_id", "value": "PlasmoDB"},
                    {"name": "source_id", "value": "PF3D7_0100100"},
                ],
                site_id="plasmodb",
            )
        # Check the PK was reordered
        call_kwargs = api.get_single_record.call_args.kwargs
        pk = call_kwargs["primary_key"]
        assert pk[0]["name"] == "source_id"
        assert pk[1]["name"] == "project_id"

    async def test_falls_back_on_record_type_info_failure(self) -> None:
        """If record type info fails, use raw PK parts."""
        svc, api = _make_service()
        api.get_record_type_info.side_effect = WDKError(detail="WDK timeout")
        api.get_single_record.return_value = WDKRecordInstance.model_validate({})

        raw_pk = [{"name": "source_id", "value": "PF3D7_0100100"}]
        await svc.get_record_detail(primary_key=raw_pk, site_id="plasmodb")

        # Should have passed raw PK through
        call_kwargs = api.get_single_record.call_args.kwargs
        assert call_kwargs["primary_key"] == raw_pk


# ===========================================================================
# Helpers: extract_pk edge cases
# ===========================================================================


class TestExtractPkEdgeCases:
    """Additional extract_pk edge cases."""

    def test_composite_pk_returns_first_value(self) -> None:
        """Only the first PK part's value is returned."""
        record = {
            "id": [
                {"name": "source_id", "value": "PF3D7_0100100"},
                {"name": "project_id", "value": "PlasmoDB"},
            ]
        }
        assert extract_pk(record) == "PF3D7_0100100"

    def test_empty_value_string(self) -> None:
        """Empty string value should still be returned (it IS a string)."""
        record = {"id": [{"name": "source_id", "value": ""}]}
        # empty string is falsy, but it's still a string
        assert extract_pk(record) == ""


# ===========================================================================
# Helpers: extract_record_ids edge cases
# ===========================================================================


class TestExtractRecordIdsEdgeCases:
    """Additional edge cases for gene ID extraction."""

    def test_duplicate_ids_preserved(self) -> None:
        """Duplicate IDs from WDK are not deduplicated at this level."""
        records = [
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
        ]
        assert extract_record_ids(records) == [
            "PF3D7_0100100",
            "PF3D7_0100100",
        ]

    def test_large_batch(self) -> None:
        """Should handle hundreds of records."""
        records = [
            {"id": [{"name": "source_id", "value": f"GENE_{i:05d}"}]}
            for i in range(500)
        ]
        ids = extract_record_ids(records)
        assert len(ids) == 500
        assert ids[0] == "GENE_00000"
        assert ids[-1] == "GENE_00499"


# ===========================================================================
# Helpers: order_primary_key edge cases
# ===========================================================================


class TestOrderPrimaryKeyEdgeCases:
    """Additional PK ordering edge cases."""

    def test_extra_parts_not_in_refs_are_dropped(self) -> None:
        """Parts not in pk_refs should be ignored."""
        parts = [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "extra_col", "value": "unknown"},
        ]
        refs = ["source_id"]
        result = order_primary_key(parts, refs, {})
        assert len(result) == 1
        assert result[0]["name"] == "source_id"

    def test_single_column_pk(self) -> None:
        """Some record types have only source_id as PK."""
        parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        refs = ["source_id"]
        result = order_primary_key(parts, refs, {})
        assert result == [{"name": "source_id", "value": "PF3D7_0100100"}]


# ===========================================================================
# Helpers: build_attribute_list edge cases
# ===========================================================================


class TestBuildAttributeListEdgeCases:
    """Additional build_attribute_list edge cases."""

    def test_large_attribute_set(self) -> None:
        """WDK gene record type can have 100+ attributes."""
        attrs = {
            f"attr_{i}": {"type": "string", "displayName": f"Attribute {i}"}
            for i in range(100)
        }
        result = build_attribute_list(attrs)
        assert len(result) == 100

    def test_numeric_types_are_sortable(self) -> None:
        attrs = [
            {"name": "score", "type": "number"},
            {"name": "gene_name", "type": "string"},
        ]
        result = build_attribute_list(attrs)
        by_name = {a["name"]: a for a in result}
        assert by_name["score"]["isSortable"] is True
        assert by_name["gene_name"]["isSortable"] is False


# ===========================================================================
# Helpers: merge_analysis_params edge cases
# ===========================================================================


class TestMergeAnalysisParamsEdgeCases:
    """Additional merge_analysis_params edge cases."""

    def test_no_parameters_in_form_meta(self) -> None:
        """If form meta has no parameters list, user params are returned."""
        form_meta = {"searchData": {}}
        result = merge_analysis_params(form_meta, {"custom": "value"})
        assert result["custom"] == "value"

    def test_non_dict_form_meta(self) -> None:
        """If form_meta is not a dict at all (None, list, etc.)."""
        result = merge_analysis_params(None, {"key": "value"})
        assert result["key"] == "value"

    def test_user_params_can_override_vocabulary_params(self) -> None:
        """User-supplied vocabulary params should override defaults."""
        form_meta = {
            "searchData": {
                "parameters": [
                    {
                        "name": "organism",
                        "initialDisplayValue": "Plasmodium falciparum 3D7",
                        "type": "single-pick-vocabulary",
                    },
                ],
            },
        }
        result = merge_analysis_params(
            form_meta,
            {"organism": "Plasmodium vivax P01"},
        )
        # Should be re-encoded as JSON array
        assert result["organism"] == '["Plasmodium vivax P01"]'

    def test_number_params_not_encoded_as_array(self) -> None:
        """Non-vocabulary params should not get JSON array encoding."""
        form_meta = {
            "searchData": {
                "parameters": [
                    {
                        "name": "pValueCutoff",
                        "initialDisplayValue": "0.05",
                        "type": "number",
                    },
                ],
            },
        }
        result = merge_analysis_params(form_meta, {"pValueCutoff": "0.01"})
        assert result["pValueCutoff"] == "0.01"
