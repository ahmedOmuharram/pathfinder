"""Tests for shared WDK helpers module.

Covers: is_sortable, is_suggested_score, extract_pk,
order_primary_key, extract_record_ids, build_attribute_list,
extract_detail_attributes, merge_analysis_params.
"""

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAttributeField,
    WDKRecordInstance,
)
from veupath_chatbot.services.wdk.helpers import (
    DETAIL_ATTRIBUTE_LIMIT,
    build_attribute_list,
    extract_detail_attributes,
    extract_pk,
    extract_record_ids,
    is_sortable,
    is_suggested_score,
    merge_analysis_params,
    order_primary_key,
)

# ---------------------------------------------------------------------------
# is_sortable
# ---------------------------------------------------------------------------


class TestIsSortable:
    """WDK numeric types are sortable; text/link types are not."""

    @pytest.mark.parametrize(
        "attr_type",
        ["number", "float", "integer", "double"],
    )
    def test_numeric_types_are_sortable(self, attr_type: str) -> None:
        assert is_sortable(attr_type) is True

    @pytest.mark.parametrize(
        "attr_type",
        ["NUMBER", "Float", "INTEGER", "DOUBLE"],
    )
    def test_case_insensitive(self, attr_type: str) -> None:
        assert is_sortable(attr_type) is True

    @pytest.mark.parametrize(
        "attr_type",
        ["string", "text", "link", "boolean"],
    )
    def test_non_numeric_types_not_sortable(self, attr_type: str) -> None:
        assert is_sortable(attr_type) is False

    def test_none_is_not_sortable(self) -> None:
        assert is_sortable(None) is False

    def test_empty_string_is_not_sortable(self) -> None:
        assert is_sortable("") is False


# ---------------------------------------------------------------------------
# is_suggested_score
# ---------------------------------------------------------------------------


class TestIsSuggestedScore:
    """Well-known score attribute names are flagged as suggested for ranking."""

    @pytest.mark.parametrize(
        "name",
        [
            "blast_score",
            "e_value",
            "evalue",
            "bit_score",
            "bitscore",
            "p_value",
            "pvalue",
            "fold_change",
            "log_fc",
            "confidence",
            "matched_result_score",
        ],
    )
    def test_known_score_keywords(self, name: str) -> None:
        assert is_suggested_score(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "BLAST_SCORE",
            "E_Value",
            "FOLD_CHANGE",
        ],
    )
    def test_case_insensitive(self, name: str) -> None:
        assert is_suggested_score(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "gene_name",
            "organism",
            "source_id",
            "description",
            "product",
        ],
    )
    def test_non_score_names(self, name: str) -> None:
        assert is_suggested_score(name) is False

    def test_empty_string(self) -> None:
        assert is_suggested_score("") is False


# ---------------------------------------------------------------------------
# extract_pk
# ---------------------------------------------------------------------------


class TestExtractPk:
    """Extracts primary key string from WDK record."""

    def test_normal_record(self) -> None:
        record = WDKRecordInstance(
            id=[{"name": "source_id", "value": "PF3D7_0100100"}],
        )
        assert extract_pk(record) == "PF3D7_0100100"

    def test_value_with_whitespace(self) -> None:
        record = WDKRecordInstance(
            id=[{"name": "source_id", "value": "  PF3D7_0100100  "}],
        )
        assert extract_pk(record) == "PF3D7_0100100"

    def test_multi_part_pk_returns_first(self) -> None:
        record = WDKRecordInstance(
            id=[
                {"name": "source_id", "value": "PF3D7_0100100"},
                {"name": "project_id", "value": "PlasmoDB"},
            ],
        )
        assert extract_pk(record) == "PF3D7_0100100"

    def test_empty_id_list(self) -> None:
        record = WDKRecordInstance(id=[])
        assert extract_pk(record) is None

    def test_missing_value_key(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id"}])
        assert extract_pk(record) is None

    def test_empty_value(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id", "value": ""}])
        assert extract_pk(record) is None

    def test_blank_value(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id", "value": "   "}])
        assert extract_pk(record) is None


# ---------------------------------------------------------------------------
# order_primary_key
# ---------------------------------------------------------------------------


class TestOrderPrimaryKey:
    """Reorders and fills PK parts to match WDK record class definition."""

    def test_reorders_to_match_refs(self) -> None:
        parts = [
            {"name": "project_id", "value": "PlasmoDB"},
            {"name": "source_id", "value": "PF3D7_0100100"},
        ]
        refs = ["source_id", "project_id"]
        result = order_primary_key(parts, refs, {})
        assert result == [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": "PlasmoDB"},
        ]

    def test_fills_missing_from_defaults(self) -> None:
        parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        refs = ["source_id", "project_id"]
        defaults = {"project_id": "PlasmoDB"}
        result = order_primary_key(parts, refs, defaults)
        assert result == [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": "PlasmoDB"},
        ]

    def test_missing_no_default_uses_empty_string(self) -> None:
        parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        refs = ["source_id", "project_id"]
        result = order_primary_key(parts, refs, {})
        assert result == [
            {"name": "source_id", "value": "PF3D7_0100100"},
            {"name": "project_id", "value": ""},
        ]

    def test_empty_parts(self) -> None:
        refs = ["source_id", "project_id"]
        defaults = {"project_id": "PlasmoDB"}
        result = order_primary_key([], refs, defaults)
        assert result == [
            {"name": "source_id", "value": ""},
            {"name": "project_id", "value": "PlasmoDB"},
        ]

    def test_empty_refs(self) -> None:
        parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        result = order_primary_key(parts, [], {})
        assert result == []

    def test_duplicate_refs(self) -> None:
        """Duplicate refs should not produce duplicate entries."""
        parts = [{"name": "source_id", "value": "PF3D7_0100100"}]
        refs = ["source_id", "source_id"]
        result = order_primary_key(parts, refs, {})
        # Each ref produces one entry
        assert len(result) == 2
        assert result[0] == {"name": "source_id", "value": "PF3D7_0100100"}
        assert result[1] == {"name": "source_id", "value": "PF3D7_0100100"}


# ---------------------------------------------------------------------------
# extract_record_ids
# ---------------------------------------------------------------------------


class TestExtractRecordIds:
    """Extracts gene/record IDs from WDK standard report records."""

    def test_normal_records(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PF3D7_0100100"}],
            ),
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PF3D7_0200200"}],
            ),
        ]
        assert extract_record_ids(records) == [
            "PF3D7_0100100",
            "PF3D7_0200200",
        ]

    def test_strips_whitespace(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "  PF3D7_0100100  "}],
            ),
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_skips_records_with_no_id(self) -> None:
        records = [
            WDKRecordInstance(
                attributes={"gene_name": "foo"},
            ),
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PF3D7_0100100"}],
            ),
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_empty_list(self) -> None:
        assert extract_record_ids([]) == []

    def test_records_with_empty_id_list(self) -> None:
        records = [WDKRecordInstance(id=[])]
        assert extract_record_ids(records) == []

    def test_skips_blank_values(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "   "}],
            ),
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PF3D7_0100100"}],
            ),
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_preferred_key_from_attributes(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PF3D7_0100100"}],
                attributes={"gene_source_id": "PF3D7_0100100"},
            ),
        ]
        result = extract_record_ids(records, preferred_key="gene_source_id")
        assert result == ["PF3D7_0100100"]

    def test_preferred_key_falls_back_to_pk(self) -> None:
        records = [
            WDKRecordInstance(
                id=[{"name": "source_id", "value": "PF3D7_0100100"}],
                attributes={"other": "value"},
            ),
        ]
        result = extract_record_ids(records, preferred_key="gene_source_id")
        assert result == ["PF3D7_0100100"]


# ---------------------------------------------------------------------------
# build_attribute_list
# ---------------------------------------------------------------------------


class TestBuildAttributeList:
    """Builds normalized attribute list from WDK attribute fields."""

    def test_basic_attributes(self) -> None:
        attrs = [
            WDKAttributeField(
                name="gene_name",
                display_name="Gene Name",
                help="The gene symbol",
                type="string",
                is_displayable=True,
            ),
            WDKAttributeField(
                name="blast_score",
                display_name="BLAST Score",
                help="Best BLAST score",
                type="number",
                is_displayable=True,
            ),
        ]
        result = build_attribute_list(attrs)
        assert len(result) == 2
        by_name = {a["name"]: a for a in result}

        gene = by_name["gene_name"]
        assert gene["displayName"] == "Gene Name"
        assert gene["help"] == "The gene symbol"
        assert gene["type"] == "string"
        assert gene["isDisplayable"] is True
        assert gene["isSortable"] is False
        assert gene["isSuggested"] is False

        blast = by_name["blast_score"]
        assert blast["displayName"] == "BLAST Score"
        assert blast["type"] == "number"
        assert blast["isSortable"] is True
        assert blast["isSuggested"] is True  # "score" keyword match

    def test_sortable_e_value(self) -> None:
        attrs = [
            WDKAttributeField(
                name="e_value",
                display_name="E-Value",
                type="double",
                is_displayable=True,
            ),
        ]
        result = build_attribute_list(attrs)
        assert len(result) == 1
        assert result[0]["name"] == "e_value"
        assert result[0]["isSortable"] is True
        assert result[0]["isSuggested"] is True

    def test_none_type_defaults(self) -> None:
        attrs = [
            WDKAttributeField(name="gene_name", display_name="Gene Name"),
        ]
        result = build_attribute_list(attrs)
        assert result[0]["type"] is None
        assert result[0]["isSortable"] is False
        assert result[0]["isSuggested"] is False

    def test_display_name_defaults_to_name(self) -> None:
        attrs = [WDKAttributeField(name="gene_name")]
        result = build_attribute_list(attrs)
        assert result[0]["displayName"] == "gene_name"

    def test_empty_display_name_defaults_to_name(self) -> None:
        attrs = [WDKAttributeField(name="gene_name", display_name="")]
        result = build_attribute_list(attrs)
        assert result[0]["displayName"] == "gene_name"

    def test_is_displayable_false_still_included(self) -> None:
        """build_attribute_list includes ALL attributes, even non-displayable ones."""
        attrs = [
            WDKAttributeField(
                name="internal",
                type="string",
                is_displayable=False,
            ),
        ]
        result = build_attribute_list(attrs)
        assert len(result) == 1
        assert result[0]["isDisplayable"] is False

    def test_empty_list(self) -> None:
        assert build_attribute_list([]) == []

    def test_suggested_requires_sortable(self) -> None:
        """isSuggested is only True when isSortable AND name matches keyword."""
        attrs = [
            # "score" keyword but string type (not sortable)
            WDKAttributeField(name="score_text", type="string"),
            # numeric but no keyword
            WDKAttributeField(name="count", type="number"),
            # numeric AND keyword
            WDKAttributeField(name="blast_score", type="number"),
        ]
        result = build_attribute_list(attrs)
        by_name = {a["name"]: a for a in result}
        assert by_name["score_text"]["isSuggested"] is False
        assert by_name["count"]["isSuggested"] is False
        assert by_name["blast_score"]["isSuggested"] is True


# ---------------------------------------------------------------------------
# extract_detail_attributes
# ---------------------------------------------------------------------------


class TestExtractDetailAttributes:
    """Extracts attribute names and display names for record detail view."""

    def test_filters_by_is_in_report(self) -> None:
        attrs = [
            WDKAttributeField(
                name="gene_name",
                display_name="Gene Name",
                is_in_report=True,
            ),
            WDKAttributeField(
                name="internal",
                display_name="Internal",
                is_in_report=False,
                is_displayable=False,
            ),
        ]
        names, display_names = extract_detail_attributes(attrs)
        assert names == ["gene_name"]
        assert display_names == {"gene_name": "Gene Name"}

    def test_falls_back_to_is_displayable(self) -> None:
        attrs = [
            WDKAttributeField(
                name="gene_name",
                display_name="Gene Name",
                is_in_report=False,
                is_displayable=True,
            ),
        ]
        names, display_names = extract_detail_attributes(attrs)
        assert names == ["gene_name"]
        assert display_names == {"gene_name": "Gene Name"}

    def test_excludes_non_reportable_non_displayable(self) -> None:
        attrs = [
            WDKAttributeField(
                name="hidden",
                display_name="Hidden",
                is_in_report=False,
                is_displayable=False,
            ),
        ]
        names, display_names = extract_detail_attributes(attrs)
        assert names == []
        assert display_names == {}

    def test_caps_at_detail_attribute_limit(self) -> None:
        attrs = [
            WDKAttributeField(
                name=f"attr_{i}",
                display_name=f"Attr {i}",
                is_in_report=True,
            )
            for i in range(DETAIL_ATTRIBUTE_LIMIT + 10)
        ]
        names, display_names = extract_detail_attributes(attrs)
        assert len(names) == DETAIL_ATTRIBUTE_LIMIT
        assert len(display_names) == DETAIL_ATTRIBUTE_LIMIT

    def test_empty_display_name_defaults_to_name(self) -> None:
        attrs = [
            WDKAttributeField(
                name="gene_name",
                display_name="",
                is_in_report=True,
            ),
        ]
        names, display_names = extract_detail_attributes(attrs)
        assert display_names["gene_name"] == "gene_name"

    def test_empty_list(self) -> None:
        names, display_names = extract_detail_attributes([])
        assert names == []
        assert display_names == {}


# ---------------------------------------------------------------------------
# merge_analysis_params
# ---------------------------------------------------------------------------


_GO_ENRICHMENT_FORM_META = {
    "searchData": {
        "parameters": [
            {
                "name": "organism",
                "initialDisplayValue": "Plasmodium falciparum 3D7",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "goAssociationsOntologies",
                "initialDisplayValue": "Biological Process",
                "type": "single-pick-vocabulary",
            },
            {
                "name": "pValueCutoff",
                "initialDisplayValue": "0.05",
                "type": "number",
            },
        ],
    },
}


class TestMergeAnalysisParams:
    """Merges WDK form defaults with user-supplied parameters."""

    def test_empty_user_params_returns_all_defaults(self) -> None:
        result = merge_analysis_params(_GO_ENRICHMENT_FORM_META, {})
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["pValueCutoff"] == "0.05"
        assert result["goAssociationsOntologies"] == '["Biological Process"]'

    def test_user_params_override_defaults(self) -> None:
        result = merge_analysis_params(
            _GO_ENRICHMENT_FORM_META,
            {"pValueCutoff": "0.01"},
        )
        assert result["pValueCutoff"] == "0.01"
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'

    def test_user_plain_string_vocab_params_get_encoded(self) -> None:
        result = merge_analysis_params(
            _GO_ENRICHMENT_FORM_META,
            {"organism": "Plasmodium vivax P01"},
        )
        assert result["organism"] == '["Plasmodium vivax P01"]'

    def test_none_form_metadata_returns_user_params(self) -> None:
        result = merge_analysis_params(None, {"pValueCutoff": "0.01"})
        assert result == {"pValueCutoff": "0.01"}

    def test_empty_form_returns_user_params(self) -> None:
        form_meta: dict[str, object] = {"searchData": {"parameters": []}}
        result = merge_analysis_params(form_meta, {"pValueCutoff": "0.01"})
        assert result == {"pValueCutoff": "0.01"}

    def test_both_empty_returns_empty(self) -> None:
        form_meta: dict[str, object] = {"searchData": {"parameters": []}}
        result = merge_analysis_params(form_meta, {})
        assert result == {}
