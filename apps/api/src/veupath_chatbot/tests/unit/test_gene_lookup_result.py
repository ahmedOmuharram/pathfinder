"""Tests for services.gene_lookup.result -- gene result building."""

from veupath_chatbot.services.gene_lookup.result import (
    DEFAULT_GENE_ATTRIBUTES,
    GeneResult,
)


class TestBuildGeneResult:
    """Tests for the standardized gene result builder."""

    def test_minimal_gene_id_only(self) -> None:
        result = GeneResult(gene_id="PF3D7_0100100")
        assert result.gene_id == "PF3D7_0100100"
        # display_name is empty string by default (transport layer handles fallback)
        assert result.display_name == ""
        assert result.organism == ""
        assert result.product == ""
        assert result.gene_name == ""
        assert result.gene_type == ""
        assert result.location == ""
        assert result.previous_ids == ""
        assert result.matched_fields is None

    def test_all_fields_populated(self) -> None:
        result = GeneResult(
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
        assert result.gene_id == "PF3D7_0100100"
        assert result.display_name == "circumsporozoite protein"
        assert result.organism == "Plasmodium falciparum 3D7"
        assert result.product == "circumsporozoite (CS) protein"
        assert result.gene_name == "CSP"
        assert result.gene_type == "protein coding"
        assert result.location == "chr1:100-200(+)"
        assert result.previous_ids == "old_id_1, old_id_2"
        assert result.matched_fields == ["gene_source_id", "gene_product"]

    def test_display_name_empty_when_product_set(self) -> None:
        """display_name is not auto-defaulted; transport layer handles fallback."""
        result = GeneResult(gene_id="PF3D7_0100100", product="some product")
        assert result.display_name == ""

    def test_display_name_empty_when_only_gene_id(self) -> None:
        result = GeneResult(gene_id="PF3D7_0100100")
        assert result.display_name == ""

    def test_display_name_explicit_value_preserved(self) -> None:
        result = GeneResult(
            gene_id="PF3D7_0100100",
            display_name="my display",
            product="some product",
        )
        assert result.display_name == "my display"

    def test_previous_ids_empty_by_default(self) -> None:
        result = GeneResult(gene_id="X", previous_ids="")
        assert result.previous_ids == ""

    def test_matched_fields_none_by_default(self) -> None:
        result = GeneResult(gene_id="X", matched_fields=None)
        assert result.matched_fields is None

    def test_matched_fields_empty_list(self) -> None:
        result = GeneResult(gene_id="X", matched_fields=[])
        assert result.matched_fields == []


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
