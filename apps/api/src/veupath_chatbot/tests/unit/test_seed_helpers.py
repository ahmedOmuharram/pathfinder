"""Tests for shared seed helper functions.

TDD: Tests written before the helpers module exists.
Each test verifies the shared helper produces the exact same output
that the seed files previously produced with their local definitions.
"""

import json

from veupath_chatbot.services.experiment.seed.helpers import (
    RNASeqOptions,
    ec_search_params,
    exon_count_params,
    gene_type_params,
    go_search_params,
    interpro_params,
    location_params,
    mol_weight_params,
    org,
    paralog_count_params,
    rnaseq_fc_params,
    signal_peptide_params,
    taxon_params,
    text_search_params,
    transmembrane_params,
)


class TestOrg:
    """Tests for org() — JSON-encodes organism name list."""

    def test_single_organism(self) -> None:
        result = org(["Plasmodium falciparum 3D7"])
        assert result == json.dumps(["Plasmodium falciparum 3D7"])
        assert result == '["Plasmodium falciparum 3D7"]'

    def test_multiple_organisms(self) -> None:
        names = ["Homo sapiens REF", "Mus musculus"]
        result = org(names)
        assert result == json.dumps(names)

    def test_empty_list(self) -> None:
        assert org([]) == "[]"


class TestGoSearchParams:
    """Tests for go_search_params() — GenesByGoTerm parameters."""

    def test_default_evidence(self) -> None:
        result = go_search_params("Plasmodium falciparum 3D7", "GO:0004672")
        assert result == {
            "organism": json.dumps(["Plasmodium falciparum 3D7"]),
            "go_term_evidence": json.dumps(["Curated", "Computed"]),
            "go_term_slim": "No",
            "go_typeahead": json.dumps(["GO:0004672"]),
            "go_term": "GO:0004672",
        }

    def test_custom_evidence(self) -> None:
        result = go_search_params(
            "Anopheles gambiae PEST",
            "GO:0003824",
            evidence=["Computed"],
        )
        assert result["go_term_evidence"] == json.dumps(["Computed"])

    def test_custom_go_term_value(self) -> None:
        # GiardiaDB uses "N/A" for go_term field
        result = go_search_params(
            "Giardia Assemblage A isolate WB",
            "GO:0005524",
            go_term_value="N/A",
        )
        assert result["go_term"] == "N/A"
        assert result["go_typeahead"] == json.dumps(["GO:0005524"])


class TestTextSearchParams:
    """Tests for text_search_params() — GenesByText parameters."""

    def test_default_product_field(self) -> None:
        result = text_search_params("Plasmodium falciparum 3D7", "kinase")
        assert result == {
            "text_search_organism": json.dumps(["Plasmodium falciparum 3D7"]),
            "text_expression": "kinase",
            "document_type": "gene",
            "text_fields": json.dumps(["product"]),
        }

    def test_custom_fields(self) -> None:
        result = text_search_params(
            "Homo sapiens REF",
            "TLR",
            fields=["name"],
        )
        assert result["text_fields"] == json.dumps(["name"])

    def test_multiple_fields(self) -> None:
        result = text_search_params(
            "Homo sapiens REF",
            "interferon",
            fields=["product", "name"],
        )
        assert result["text_fields"] == json.dumps(["product", "name"])


class TestSignalPeptideParams:
    """Tests for signal_peptide_params() — GenesWithSignalPeptide parameters."""

    def test_basic(self) -> None:
        result = signal_peptide_params("Toxoplasma gondii ME49")
        assert result == {
            "organism": json.dumps(["Toxoplasma gondii ME49"]),
        }


class TestTransmembraneParams:
    """Tests for transmembrane_params() — GenesByTransmembraneDomains parameters."""

    def test_with_string_args(self) -> None:
        result = transmembrane_params("Anopheles gambiae PEST", "1", "99")
        assert result == {
            "organism": json.dumps(["Anopheles gambiae PEST"]),
            "min_tm": "1",
            "max_tm": "99",
        }

    def test_different_values(self) -> None:
        result = transmembrane_params("Leishmania major strain Friedlin", "3", "20")
        assert result["min_tm"] == "3"
        assert result["max_tm"] == "20"


class TestMolWeightParams:
    """Tests for mol_weight_params() — GenesByMolecularWeight parameters."""

    def test_basic(self) -> None:
        result = mol_weight_params("Anopheles gambiae PEST", "10000", "50000")
        assert result == {
            "organism": json.dumps(["Anopheles gambiae PEST"]),
            "min_molecular_weight": "10000",
            "max_molecular_weight": "50000",
        }


class TestEcSearchParams:
    """Tests for ec_search_params() — GenesByEcNumber parameters."""

    def test_basic(self) -> None:
        result = ec_search_params(
            "Plasmodium falciparum 3D7",
            ec_number="2.7.11.1",
            ec_sources=["KEGG_Enzyme", "Uniprot"],
        )
        assert result == {
            "organism": json.dumps(["Plasmodium falciparum 3D7"]),
            "ec_source": json.dumps(["KEGG_Enzyme", "Uniprot"]),
            "ec_number_pattern": "2.7.11.1",
            "ec_wildcard": "No",
        }

    def test_custom_wildcard(self) -> None:
        result = ec_search_params(
            "Toxoplasma gondii ME49",
            ec_number="2.7.11.1",
            ec_sources=["KEGG_Enzyme"],
            ec_wildcard="N/A",
        )
        assert result["ec_wildcard"] == "N/A"


class TestGeneTypeParams:
    """Tests for gene_type_params() — GenesByGeneType parameters."""

    def test_default_protein_coding(self) -> None:
        result = gene_type_params("Homo sapiens REF")
        assert result == {
            "organism": json.dumps(["Homo sapiens REF"]),
            "geneType": json.dumps(["protein coding"]),
            "includePseudogenes": "No",
        }

    def test_custom_gene_type(self) -> None:
        result = gene_type_params("Homo sapiens REF", gene_type="rRNA")
        assert result["geneType"] == json.dumps(["rRNA"])


class TestInterproParams:
    """Tests for interpro_params() — GenesByInterproDomain parameters."""

    def test_basic(self) -> None:
        result = interpro_params("Anopheles gambiae PEST", "Pfam", "PF00069")
        assert result == {
            "organism": json.dumps(["Anopheles gambiae PEST"]),
            "domain_database": "Pfam",
            "domain_typeahead": "PF00069",
            "domain_accession": "*",
        }


class TestLocationParams:
    """Tests for location_params() — GenesByLocation parameters."""

    def test_basic(self) -> None:
        result = location_params("Anopheles gambiae PEST", "2L", "1", "10000000")
        assert result == {
            "organismSinglePick": json.dumps(["Anopheles gambiae PEST"]),
            "chromosomeOptional": "2L",
            "sequenceId": "",
            "start_point": "1",
            "end_point": "10000000",
        }


class TestExonCountParams:
    """Tests for exon_count_params() — GenesByExonCount parameters."""

    def test_basic(self) -> None:
        result = exon_count_params("Anopheles gambiae PEST", "5", "100")
        assert result == {
            "organism": json.dumps(["Anopheles gambiae PEST"]),
            "scope": "Gene",
            "num_exons_gte": "5",
            "num_exons_lte": "100",
        }


class TestTaxonParams:
    """Tests for taxon_params() — GenesByTaxon parameters."""

    def test_basic(self) -> None:
        result = taxon_params("Anopheles gambiae PEST")
        assert result == {
            "organism": json.dumps(["Anopheles gambiae PEST"]),
        }


class TestRnaseqFcParams:
    """Tests for rnaseq_fc_params() — RNA-Seq fold-change parameters."""

    def test_basic(self) -> None:
        result = rnaseq_fc_params(
            dataset_url="https://example.org/dataset",
            profileset="Some experiment",
            direction="up-regulated",
            ref_samples=["Control"],
            comp_samples=["Treatment"],
            options=RNASeqOptions(fold_change="2", hard_floor="100.0"),
        )
        assert result == {
            "dataset_url": "https://example.org/dataset",
            "profileset_generic": "Some experiment",
            "regulated_dir": "up-regulated",
            "samples_fc_ref_generic": json.dumps(["Control"]),
            "min_max_avg_ref": "average1",
            "samples_fc_comp_generic": json.dumps(["Treatment"]),
            "min_max_avg_comp": "average1",
            "fold_change": "2",
            "hard_floor": "100.0",
            "protein_coding_only": "yes",
        }

    def test_custom_ops(self) -> None:
        result = rnaseq_fc_params(
            dataset_url="https://example.org/dataset",
            profileset="Experiment",
            direction="down-regulated",
            ref_samples=["A", "B"],
            comp_samples=["C"],
            options=RNASeqOptions(
                fold_change="3",
                hard_floor="50.0",
                protein_coding="no",
                ref_op="max",
                comp_op="min",
            ),
        )
        assert result["min_max_avg_ref"] == "max"
        assert result["min_max_avg_comp"] == "min"
        assert result["protein_coding_only"] == "no"


class TestParalogCountParams:
    """Tests for paralog_count_params() — GenesByParalogCount parameters."""

    def test_basic(self) -> None:
        result = paralog_count_params("Giardia Assemblage A isolate WB", "5", "500")
        assert result == {
            "organism": json.dumps(["Giardia Assemblage A isolate WB"]),
            "num_paralogs": json.dumps({"min": "5", "max": "500"}),
        }
