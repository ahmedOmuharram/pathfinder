"""Unit tests for search scoring, filtering, and annotation."""

from pathfinder.services.catalog.searches import (
    annotate_search,
    is_chooser_search,
    score_search,
)


def test_search_name_match_beats_description_match():
    """Term in searchName should score higher than same term in description."""
    result_name = score_search(
        query_terms=["strand", "specific"],
        keywords=[],
        search_name="GenesByRNASeqpfal3D7_Su_strand_specific_rnaSeq_RSRCPercentile",
        display_name="Strand specific transcriptomes RNA-Seq (percentile)",
        description="Find genes by RNA-Seq expression percentile.",
    )
    result_desc = score_search(
        query_terms=["strand", "specific"],
        keywords=[],
        search_name="GenesByRNASeqpfal3D7_Lasonder_Bartfai_Gametocytes_ebi_rnaSeq_RSRCPercentile",
        display_name="Gametocyte Transcriptomes RNA-Seq (percentile)",
        description="Strand specific analysis of something.",
    )
    assert result_name > result_desc


def test_keyword_match_on_search_name_is_massive_boost():
    """Keyword matching against urlSegment should dominate scoring."""
    with_kw = score_search(
        query_terms=["gametocyte"],
        keywords=["Su_strand_specific"],
        search_name="GenesByRNASeqpfal3D7_Su_strand_specific_rnaSeq_RSRCPercentile",
        display_name="Strand specific transcriptomes",
        description="",
    )
    without_kw = score_search(
        query_terms=["gametocyte", "strand", "specific"],
        keywords=[],
        search_name="GenesByRNASeqpfal3D7_Lasonder_Bartfai_Gametocytes_ebi_rnaSeq_RSRCPercentile",
        display_name="Gametocyte Transcriptomes",
        description="",
    )
    assert with_kw > without_kw


def test_short_terms_ignored():
    """Terms < 3 chars should not contribute to query scoring."""
    score_with_short = score_search(
        query_terms=["p", "su", "rna"],
        keywords=[],
        search_name="SomeSearch",
        display_name="Some RNA search",
        description="",
    )
    score_no_short = score_search(
        query_terms=["rna"],
        keywords=[],
        search_name="SomeSearch",
        display_name="Some RNA search",
        description="",
    )
    assert score_with_short == score_no_short


def test_idf_boosts_rare_terms():
    """Rare terms should score higher than common terms."""
    score_rare = score_search(
        query_terms=["su_strand"],
        keywords=[],
        search_name="GenesByRNASeqpfal3D7_Su_strand_specific_rnaSeq_RSRCPercentile",
        display_name="Strand specific",
        description="",
        corpus_doc_count=300,
        corpus_term_counts={"su_strand": 2},
    )
    score_common = score_search(
        query_terms=["rna"],
        keywords=[],
        search_name="GenesByRNASeqpfal3D7_Su_strand_specific_rnaSeq_RSRCPercentile",
        display_name="Strand specific",
        description="",
        corpus_doc_count=300,
        corpus_term_counts={"rna": 200},
    )
    assert score_rare > score_common


def test_zero_score_when_no_match():
    """No matching terms should return 0."""
    score = score_search(
        query_terms=["xyznothing"],
        keywords=[],
        search_name="GenesByGoTerm",
        display_name="GO Term",
        description="Find genes by Gene Ontology.",
    )
    assert score == 0.0


# --- Filtering ---


def test_chooser_searches_filtered():
    """Searches with hideOperation property should be filtered out."""
    chooser = {
        "properties": {"websiteProperties": ["hideOperation", "hideAttrDescr"]},
        "paramNames": [],
    }
    assert is_chooser_search(chooser) is True

    real = {"properties": {}, "paramNames": ["organism", "min_tm"]}
    assert is_chooser_search(real) is False


# --- Annotation ---


def test_result_annotated_with_category():
    """Results should include a category field from displayCategory."""
    search = {
        "urlSegment": "GenesByRNASeqpfal3D7_foo_RSRCPercentile",
        "displayName": "Foo RNA-Seq (percentile)",
        "properties": {"displayCategory": ["percentile"]},
    }
    annotated = annotate_search(search)
    assert annotated["category"] == "percentile"


def test_result_annotated_with_record_direction():
    """Results should indicate what they return (genes vs SNPs)."""
    gene_search = {
        "urlSegment": "GenesByNgsSnps",
        "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
    }
    snp_search = {
        "urlSegment": "NgsSnpsByGeneIds",
        "recordClassName": "SnpRecordClasses.SnpRecordClass",
    }
    assert annotate_search(gene_search)["returns"] == "genes/transcripts"
    assert annotate_search(snp_search)["returns"] == "SNPs"
