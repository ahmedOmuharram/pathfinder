"""Extended tests for WDK step results service and enrichment service.

Covers: attribute listing edge cases, record browsing with empty/large results,
distribution fallback, analysis type discovery, record detail PK ordering,
and enrichment edge cases.
"""

from unittest.mock import AsyncMock, MagicMock

import pydantic
import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKAttributeField,
    WDKColumnDistribution,
    WDKHistogramBin,
    WDKHistogramStatistics,
    WDKRecordInstance,
    WDKRecordType,
    WDKStepAnalysisType,
)
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
        api.get_record_type_info.return_value = WDKRecordType.model_validate(
            {
                "urlSegment": "gene",
                "attributes": [
                    {"name": "gene_name", "displayName": "Gene Name", "type": "string"},
                ],
            }
        )
        result = await svc.get_attributes()
        assert result["recordType"] == "gene"
        attrs = result["attributes"]
        assert isinstance(attrs, list)
        assert len(attrs) == 1
        first = attrs[0]
        assert isinstance(first, dict)
        assert first["name"] == "gene_name"

    async def test_falls_back_to_attributes_map(self) -> None:
        """Some WDK deployments use 'attributesMap' dict format."""
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate(
            {
                "urlSegment": "gene",
                "attributesMap": {
                    "gene_name": {
                        "name": "gene_name",
                        "displayName": "Gene Name",
                        "type": "string",
                    },
                },
            }
        )
        result = await svc.get_attributes()
        assert len(result["attributes"]) == 1

    async def test_empty_attributes(self) -> None:
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate(
            {
                "urlSegment": "gene",
                "attributes": [],
            }
        )
        result = await svc.get_attributes()
        assert result["attributes"] == []

    async def test_no_attributes_key(self) -> None:
        """If neither 'attributes' nor 'attributesMap' exists, return empty."""
        svc, api = _make_service()
        api.get_record_type_info.return_value = WDKRecordType.model_validate(
            {
                "urlSegment": "gene",
            }
        )
        result = await svc.get_attributes()
        assert result["attributes"] == []


# ===========================================================================
# StepResultsService -get_records
# ===========================================================================


class TestGetRecords:
    """Record browsing edge cases."""

    async def test_default_pagination(self) -> None:
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate(
            {
                "records": [],
                "meta": {"totalCount": 0},
            }
        )
        result = await svc.get_records()
        assert result.records == []

    async def test_lowercase_direction_rejected(self) -> None:
        """WDKSortDirection is Literal['ASC', 'DESC'] — lowercase is invalid.

        Callers (e.g. ai_analysis_tools) must uppercase before calling get_records.
        """
        svc, _api = _make_service()
        with pytest.raises(pydantic.ValidationError, match="Input should be 'ASC' or 'DESC'"):
            await svc.get_records(sort="col", direction="asc")

    async def test_missing_records_key_defaults_empty(self) -> None:
        """WDKAnswer defaults 'records' to empty list when omitted."""
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate(
            {
                "meta": {"totalCount": 0},
            }
        )
        result = await svc.get_records()
        assert result.records == []

    async def test_empty_meta_defaults(self) -> None:
        """WDKAnswerMeta defaults all fields when meta dict is empty."""
        svc, api = _make_service()
        api.get_step_records.return_value = WDKAnswer.model_validate(
            {
                "records": [],
                "meta": {},
            }
        )
        result = await svc.get_records()
        assert result.meta.total_count == 0


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
            WDKStepAnalysisType(
                name="pathway-enrichment", display_name="Pathway Enrichment"
            ),
        ]
        result = await svc.list_analysis_types()
        assert len(result["analysisTypes"]) == 2


# ===========================================================================
# StepResultsService -get_record_detail
# ===========================================================================




# ===========================================================================
# Helpers: extract_pk edge cases
# ===========================================================================


class TestExtractPkEdgeCases:
    """Additional extract_pk edge cases."""

    def test_composite_pk_returns_first_value(self) -> None:
        """Only the first PK part's value is returned."""
        record = WDKRecordInstance.model_validate(
            {
                "id": [
                    {"name": "source_id", "value": "PF3D7_0100100"},
                    {"name": "project_id", "value": "PlasmoDB"},
                ]
            }
        )
        assert extract_pk(record) == "PF3D7_0100100"

    def test_empty_value_string(self) -> None:
        """Empty/whitespace PK values return None — an empty PK is meaningless."""
        record = WDKRecordInstance.model_validate(
            {
                "id": [{"name": "source_id", "value": ""}],
            }
        )
        assert extract_pk(record) is None


# ===========================================================================
# Helpers: extract_record_ids edge cases
# ===========================================================================


class TestExtractRecordIdsEdgeCases:
    """Additional edge cases for gene ID extraction."""

    def test_duplicate_ids_preserved(self) -> None:
        """Duplicate IDs from WDK are not deduplicated at this level."""
        records = [
            WDKRecordInstance.model_validate(
                {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]}
            ),
            WDKRecordInstance.model_validate(
                {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]}
            ),
        ]
        assert extract_record_ids(records) == [
            "PF3D7_0100100",
            "PF3D7_0100100",
        ]

    def test_large_batch(self) -> None:
        """Should handle hundreds of records."""
        records = [
            WDKRecordInstance.model_validate(
                {"id": [{"name": "source_id", "value": f"GENE_{i:05d}"}]}
            )
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
        attrs = [
            WDKAttributeField(
                name=f"attr_{i}", display_name=f"Attribute {i}", type="string"
            )
            for i in range(100)
        ]
        result = build_attribute_list(attrs)
        assert len(result) == 100

    def test_numeric_types_are_sortable(self) -> None:
        attrs = [
            WDKAttributeField(name="score", type="number"),
            WDKAttributeField(name="gene_name", type="string"),
        ]
        result = build_attribute_list(attrs)
        by_name: dict[str, dict[str, object]] = {}
        for a in result:
            assert isinstance(a, dict)
            name = a["name"]
            assert isinstance(name, str)
            by_name[name] = a  # type narrowed to dict
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
