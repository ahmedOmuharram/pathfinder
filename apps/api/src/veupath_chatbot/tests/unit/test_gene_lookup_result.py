"""Tests for services.gene_lookup.result -- gene result building."""

from veupath_chatbot.services.gene_lookup.result import (
    DEFAULT_GENE_ATTRIBUTES,
    GeneResultInput,
    build_gene_result,
)


class TestBuildGeneResult:
    """Tests for the standardized gene result builder."""

    def test_minimal_gene_id_only(self) -> None:
        result = build_gene_result(GeneResultInput(gene_id="PF3D7_0100100"))
        assert result["geneId"] == "PF3D7_0100100"
        # displayName falls back to gene_id when product is empty
        assert result["displayName"] == "PF3D7_0100100"
        assert result["organism"] == ""
        assert result["product"] == ""
        assert result["geneName"] == ""
        assert result["geneType"] == ""
        assert result["location"] == ""
        # No previousIds or matchedFields when not provided
        assert "previousIds" not in result
        assert "matchedFields" not in result

    def test_all_fields_populated(self) -> None:
        result = build_gene_result(
            GeneResultInput(
                gene_id="PF3D7_0100100",
                display_name="circumsporozoite protein",
                organism="Plasmodium falciparum 3D7",
                product="circumsporozoite (CS) protein",
                gene_name="CSP",
                gene_type="protein coding",
                location="chr1:100-200(+)",
                previous_ids="old_id_1, old_id_2",
                matched_fields=["gene_source_id", "gene_product"],
            )
        )
        assert result["geneId"] == "PF3D7_0100100"
        assert result["displayName"] == "circumsporozoite protein"
        assert result["organism"] == "Plasmodium falciparum 3D7"
        assert result["product"] == "circumsporozoite (CS) protein"
        assert result["geneName"] == "CSP"
        assert result["geneType"] == "protein coding"
        assert result["location"] == "chr1:100-200(+)"
        assert result["previousIds"] == "old_id_1, old_id_2"
        assert result["matchedFields"] == ["gene_source_id", "gene_product"]

    def test_display_name_falls_back_to_product(self) -> None:
        result = build_gene_result(
            GeneResultInput(gene_id="PF3D7_0100100", product="some product")
        )
        assert result["displayName"] == "some product"

    def test_display_name_falls_back_to_gene_id(self) -> None:
        result = build_gene_result(GeneResultInput(gene_id="PF3D7_0100100"))
        assert result["displayName"] == "PF3D7_0100100"

    def test_display_name_prefers_explicit_over_product(self) -> None:
        result = build_gene_result(
            GeneResultInput(
                gene_id="PF3D7_0100100",
                display_name="my display",
                product="some product",
            )
        )
        assert result["displayName"] == "my display"

    def test_previous_ids_omitted_when_empty(self) -> None:
        result = build_gene_result(GeneResultInput(gene_id="X", previous_ids=""))
        assert "previousIds" not in result

    def test_matched_fields_omitted_when_none(self) -> None:
        result = build_gene_result(GeneResultInput(gene_id="X", matched_fields=None))
        assert "matchedFields" not in result

    def test_matched_fields_included_when_empty_list(self) -> None:
        result = build_gene_result(GeneResultInput(gene_id="X", matched_fields=[]))
        assert result["matchedFields"] == []


class TestDefaultGeneAttributes:
    """Ensure the default attribute list is correct for WDK requests."""

    def test_contains_primary_key(self) -> None:
        assert "primary_key" in DEFAULT_GENE_ATTRIBUTES

    def test_contains_gene_source_id(self) -> None:
        assert "gene_source_id" in DEFAULT_GENE_ATTRIBUTES

    def test_contains_organism(self) -> None:
        assert "organism" in DEFAULT_GENE_ATTRIBUTES

    def test_contains_gene_product(self) -> None:
        assert "gene_product" in DEFAULT_GENE_ATTRIBUTES

    def test_contains_gene_name(self) -> None:
        assert "gene_name" in DEFAULT_GENE_ATTRIBUTES

    def test_contains_gene_type(self) -> None:
        assert "gene_type" in DEFAULT_GENE_ATTRIBUTES
