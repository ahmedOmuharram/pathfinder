"""Unit tests for WDK enrichment row and response models.

Verifies that Pydantic models correctly parse real WDK enrichment plugin
output — where ALL values are strings (Java plugins serialize via
``json.put(key, stringValue)``).

Real data verified from live PlasmoDB 2026-03-22.
"""

import pytest
from pydantic import ValidationError

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKEnrichmentResponse,
    WDKEnrichmentRowBase,
    WDKGoEnrichmentRow,
    WDKPathwayEnrichmentRow,
    WDKWordEnrichmentRow,
)

# ---------------------------------------------------------------------------
# Real WDK GO enrichment row (PlasmoDB 2026-03-22)
# ---------------------------------------------------------------------------
GO_ROW_JSON: dict[str, str] = {
    "goId": "GO:0016310",
    "goTerm": "phosphorylation",
    "bgdGenes": "111",
    "resultGenes": (
        "<a href='/a/app/search/transcript/GeneByLocusTag"
        "?param.ds_gene_ids.idList=PF3D7_0102600,PF3D7_0107600"
        "&autoRun=1'>2</a>"
    ),
    "percentInResult": "89.2",
    "foldEnrich": "22.97",
    "oddsRatio": "832.99",
    "pValue": "2.49554207041e-147",
    "benjamini": "5.46523713419e-145",
    "bonferroni": "5.46523713419e-145",
}


class TestWDKGoEnrichmentRow:
    """Tests for WDKGoEnrichmentRow — GO enrichment plugin output."""

    def test_parse_real_row(self) -> None:
        row = WDKGoEnrichmentRow.model_validate(GO_ROW_JSON)
        assert row.go_id == "GO:0016310"
        assert row.go_term == "phosphorylation"
        assert row.bgd_genes == "111"
        assert row.result_genes.startswith("<a href=")
        assert row.percent_in_result == "89.2"
        assert row.fold_enrich == "22.97"
        assert row.odds_ratio == "832.99"
        assert row.p_value == "2.49554207041e-147"
        assert row.benjamini == "5.46523713419e-145"
        assert row.bonferroni == "5.46523713419e-145"

    def test_defaults_for_missing_optional_fields(self) -> None:
        row = WDKGoEnrichmentRow.model_validate(
            {"goId": "GO:0000001", "goTerm": "test term"},
        )
        assert row.go_id == "GO:0000001"
        assert row.go_term == "test term"
        assert row.bgd_genes == "0"
        assert row.result_genes == "0"
        assert row.percent_in_result == "0"
        assert row.fold_enrich == "0"
        assert row.odds_ratio == "0"
        assert row.p_value == "1"
        assert row.benjamini == "1"
        assert row.bonferroni == "1"

    def test_rejects_missing_go_id(self) -> None:
        with pytest.raises(ValidationError, match="goId"):
            WDKGoEnrichmentRow.model_validate(
                {"goTerm": "phosphorylation", "bgdGenes": "10"},
            )

    def test_rejects_missing_go_term(self) -> None:
        with pytest.raises(ValidationError, match="goTerm"):
            WDKGoEnrichmentRow.model_validate(
                {"goId": "GO:0016310", "bgdGenes": "10"},
            )

    def test_ignores_extra_fields(self) -> None:
        data = {**GO_ROW_JSON, "unknownPluginField": "should be ignored"}
        row = WDKGoEnrichmentRow.model_validate(data)
        assert row.go_id == "GO:0016310"
        assert not hasattr(row, "unknown_plugin_field")

    def test_frozen(self) -> None:
        row = WDKGoEnrichmentRow.model_validate(GO_ROW_JSON)
        with pytest.raises(ValidationError):
            row.go_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestWDKPathwayEnrichmentRow
# ---------------------------------------------------------------------------
PATHWAY_ROW_JSON: dict[str, str] = {
    "pathwayId": "ec00010",
    "pathwayName": "Glycolysis / Gluconeogenesis",
    "pathwaySource": "KEGG",
    "bgdGenes": "42",
    "resultGenes": "5",
    "percentInResult": "11.9",
    "foldEnrich": "3.21",
    "oddsRatio": "4.56",
    "pValue": "0.001",
    "benjamini": "0.05",
    "bonferroni": "0.12",
}


class TestWDKPathwayEnrichmentRow:
    """Tests for WDKPathwayEnrichmentRow — pathway enrichment plugin output."""

    def test_parse_pathway_row(self) -> None:
        row = WDKPathwayEnrichmentRow.model_validate(PATHWAY_ROW_JSON)
        assert row.pathway_id == "ec00010"
        assert row.pathway_name == "Glycolysis / Gluconeogenesis"
        assert row.pathway_source == "KEGG"
        assert row.bgd_genes == "42"
        assert row.p_value == "0.001"

    def test_pathway_source_defaults_to_empty(self) -> None:
        row = WDKPathwayEnrichmentRow.model_validate(
            {"pathwayId": "ec00020", "pathwayName": "Citrate cycle"},
        )
        assert row.pathway_source == ""

    def test_rejects_missing_pathway_id(self) -> None:
        with pytest.raises(ValidationError, match="pathwayId"):
            WDKPathwayEnrichmentRow.model_validate(
                {"pathwayName": "Glycolysis"},
            )


# ---------------------------------------------------------------------------
# TestWDKWordEnrichmentRow
# ---------------------------------------------------------------------------
WORD_ROW_JSON: dict[str, str] = {
    "word": "kinase",
    "pathwayName": "protein kinase activity",
    "bgdGenes": "200",
    "resultGenes": "15",
    "percentInResult": "7.5",
    "foldEnrich": "2.1",
    "oddsRatio": "3.0",
    "pValue": "0.0005",
    "benjamini": "0.01",
    "bonferroni": "0.03",
}


class TestWDKWordEnrichmentRow:
    """Tests for WDKWordEnrichmentRow — word enrichment plugin output."""

    def test_parse_word_row(self) -> None:
        row = WDKWordEnrichmentRow.model_validate(WORD_ROW_JSON)
        assert row.word == "kinase"
        assert row.pathway_name == "protein kinase activity"
        assert row.bgd_genes == "200"
        assert row.p_value == "0.0005"

    def test_word_required(self) -> None:
        with pytest.raises(ValidationError, match="word"):
            WDKWordEnrichmentRow.model_validate(
                {"pathwayName": "some description"},
            )

    def test_pathway_name_defaults_to_empty(self) -> None:
        row = WDKWordEnrichmentRow.model_validate({"word": "apicoplast"})
        assert row.pathway_name == ""


# ---------------------------------------------------------------------------
# TestWDKEnrichmentRowBase
# ---------------------------------------------------------------------------
class TestWDKEnrichmentRowBase:
    """Tests for the shared base fields across enrichment types."""

    def test_all_defaults(self) -> None:
        row = WDKEnrichmentRowBase.model_validate({})
        assert row.bgd_genes == "0"
        assert row.result_genes == "0"
        assert row.percent_in_result == "0"
        assert row.fold_enrich == "0"
        assert row.odds_ratio == "0"
        assert row.p_value == "1"
        assert row.benjamini == "1"
        assert row.bonferroni == "1"

    def test_camel_case_aliases(self) -> None:
        row = WDKEnrichmentRowBase.model_validate(
            {"bgdGenes": "50", "resultGenes": "10", "foldEnrich": "5.0"},
        )
        assert row.bgd_genes == "50"
        assert row.result_genes == "10"
        assert row.fold_enrich == "5.0"


# ---------------------------------------------------------------------------
# TestWDKEnrichmentResponse
# ---------------------------------------------------------------------------
class TestWDKEnrichmentResponse:
    """Tests for WDKEnrichmentResponse — the envelope around enrichment results."""

    def test_parse_full_response(self) -> None:
        response = WDKEnrichmentResponse.model_validate(
            {
                "resultData": [GO_ROW_JSON],
                "downloadPath": "/data/enrichment_123.tsv",
                "pvalueCutoff": "0.05",
            },
        )
        assert len(response.result_data) == 1
        assert response.result_data[0]["goId"] == "GO:0016310"
        assert response.download_path == "/data/enrichment_123.tsv"
        assert response.pvalue_cutoff == "0.05"

    def test_empty_result_data(self) -> None:
        response = WDKEnrichmentResponse.model_validate(
            {"resultData": [], "downloadPath": "", "pvalueCutoff": "0.05"},
        )
        assert response.result_data == []

    def test_defaults_for_missing_fields(self) -> None:
        response = WDKEnrichmentResponse.model_validate({})
        assert response.result_data == []
        assert response.download_path == ""
        assert response.pvalue_cutoff == ""

    def test_ignores_plugin_specific_fields(self) -> None:
        response = WDKEnrichmentResponse.model_validate(
            {
                "resultData": [],
                "downloadPath": "/data/x.tsv",
                "pvalueCutoff": "0.05",
                "goTermBaseUrl": "https://amigo.org/",
                "accessToken": "abc123",
                "contextHash": "deadbeef",
            },
        )
        assert response.download_path == "/data/x.tsv"
        assert not hasattr(response, "go_term_base_url")
        assert not hasattr(response, "access_token")
        assert not hasattr(response, "context_hash")
