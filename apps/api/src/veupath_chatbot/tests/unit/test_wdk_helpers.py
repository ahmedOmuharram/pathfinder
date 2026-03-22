"""Tests for shared WDK helpers module.

Covers: is_sortable, is_suggested_score, extract_pk,
order_primary_key, extract_record_ids, build_attribute_list, merge_analysis_params.
"""

import pytest

from veupath_chatbot.services.wdk.helpers import (
    build_attribute_list,
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
        record = {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]}
        assert extract_pk(record) == "PF3D7_0100100"

    def test_value_with_whitespace(self) -> None:
        record = {"id": [{"name": "source_id", "value": "  PF3D7_0100100  "}]}
        assert extract_pk(record) == "PF3D7_0100100"

    def test_multi_part_pk_returns_first(self) -> None:
        record = {
            "id": [
                {"name": "source_id", "value": "PF3D7_0100100"},
                {"name": "project_id", "value": "PlasmoDB"},
            ]
        }
        assert extract_pk(record) == "PF3D7_0100100"

    def test_empty_id_list(self) -> None:
        record: dict[str, object] = {"id": []}
        assert extract_pk(record) is None

    def test_missing_id_key(self) -> None:
        record: dict[str, object] = {"attributes": {"gene_name": "foo"}}
        assert extract_pk(record) is None

    def test_id_is_not_list(self) -> None:
        record: dict[str, object] = {"id": "not_a_list"}
        assert extract_pk(record) is None

    def test_first_element_not_dict(self) -> None:
        record: dict[str, object] = {"id": ["string_element"]}
        assert extract_pk(record) is None

    def test_missing_value_key(self) -> None:
        record = {"id": [{"name": "source_id"}]}
        assert extract_pk(record) is None

    def test_value_not_string(self) -> None:
        record = {"id": [{"name": "source_id", "value": 12345}]}
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
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
            {"id": [{"name": "source_id", "value": "PF3D7_0200200"}]},
        ]
        assert extract_record_ids(records) == [
            "PF3D7_0100100",
            "PF3D7_0200200",
        ]

    def test_strips_whitespace(self) -> None:
        records = [
            {"id": [{"name": "source_id", "value": "  PF3D7_0100100  "}]},
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_skips_non_dict_records(self) -> None:
        records: list[object] = [
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
            "not_a_dict",
            42,
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_skips_records_with_no_id(self) -> None:
        records: list[object] = [
            {"attributes": {"gene_name": "foo"}},
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_empty_list(self) -> None:
        assert extract_record_ids([]) == []

    def test_records_with_empty_id_list(self) -> None:
        records: list[object] = [{"id": []}]
        assert extract_record_ids(records) == []

    def test_skips_non_string_values(self) -> None:
        records: list[object] = [
            {"id": [{"name": "source_id", "value": 12345}]},
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]

    def test_skips_blank_values(self) -> None:
        records: list[object] = [
            {"id": [{"name": "source_id", "value": "   "}]},
            {"id": [{"name": "source_id", "value": "PF3D7_0100100"}]},
        ]
        assert extract_record_ids(records) == ["PF3D7_0100100"]


# ---------------------------------------------------------------------------
# build_attribute_list
# ---------------------------------------------------------------------------


class TestBuildAttributeList:
    """Builds normalized attribute list from WDK record type info."""

    def test_dict_format(self) -> None:
        attrs_raw = {
            "gene_name": {
                "displayName": "Gene Name",
                "help": "The gene symbol",
                "type": "string",
                "isDisplayable": True,
            },
            "blast_score": {
                "displayName": "BLAST Score",
                "help": "Best BLAST score",
                "type": "number",
                "isDisplayable": True,
            },
        }
        result = build_attribute_list(attrs_raw)
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

    def test_list_format(self) -> None:
        attrs_raw = [
            {
                "name": "e_value",
                "displayName": "E-Value",
                "type": "double",
                "isDisplayable": True,
            },
        ]
        result = build_attribute_list(attrs_raw)
        assert len(result) == 1
        assert result[0]["name"] == "e_value"
        assert result[0]["isSortable"] is True
        assert result[0]["isSuggested"] is True

    def test_dict_format_filters_non_dict_meta(self) -> None:
        attrs_raw = {
            "gene_name": {"type": "string"},
            "bad": "not_a_dict",
        }
        result = build_attribute_list(attrs_raw)
        assert len(result) == 1
        assert result[0]["name"] == "gene_name"

    def test_list_format_filters_non_dict_entries(self) -> None:
        attrs_raw = [
            {"name": "gene_name", "type": "string"},
            "not_a_dict",
            42,
        ]
        result = build_attribute_list(attrs_raw)
        assert len(result) == 1
        assert result[0]["name"] == "gene_name"

    def test_none_type_defaults(self) -> None:
        attrs_raw = {"gene_name": {"displayName": "Gene Name"}}
        result = build_attribute_list(attrs_raw)
        assert result[0]["type"] is None
        assert result[0]["isSortable"] is False
        assert result[0]["isSuggested"] is False

    def test_display_name_defaults_to_name(self) -> None:
        attrs_raw = {"gene_name": {}}
        result = build_attribute_list(attrs_raw)
        assert result[0]["displayName"] == "gene_name"

    def test_is_displayable_defaults_to_true(self) -> None:
        attrs_raw = {"gene_name": {"type": "string"}}
        result = build_attribute_list(attrs_raw)
        assert result[0]["isDisplayable"] is True

    def test_is_displayable_false_still_included(self) -> None:
        """build_attribute_list includes ALL attributes, even non-displayable ones."""
        attrs_raw = {"internal": {"type": "string", "isDisplayable": False}}
        result = build_attribute_list(attrs_raw)
        assert len(result) == 1
        assert result[0]["isDisplayable"] is False

    def test_empty_dict(self) -> None:
        assert build_attribute_list({}) == []

    def test_empty_list(self) -> None:
        assert build_attribute_list([]) == []

    def test_none_input(self) -> None:
        assert build_attribute_list(None) == []

    def test_suggested_requires_sortable(self) -> None:
        """isSuggested is only True when isSortable AND name matches keyword."""
        attrs_raw = {
            # "score" keyword but string type (not sortable)
            "score_text": {"type": "string"},
            # numeric but no keyword
            "count": {"type": "number"},
            # numeric AND keyword
            "blast_score": {"type": "number"},
        }
        result = build_attribute_list(attrs_raw)
        by_name = {a["name"]: a for a in result}
        assert by_name["score_text"]["isSuggested"] is False
        assert by_name["count"]["isSuggested"] is False
        assert by_name["blast_score"]["isSuggested"] is True

    def test_list_format_name_defaults_to_empty(self) -> None:
        attrs_raw = [{"type": "string"}]
        result = build_attribute_list(attrs_raw)
        assert len(result) == 1
        assert result[0]["name"] == ""


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
