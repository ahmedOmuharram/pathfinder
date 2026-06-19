"""Enrichment parser: transform real WDK plugin responses (all-string,
camelCase rows under ``resultData``) into typed ``EnrichmentTerm``s. Field
names + shapes verified against live PlasmoDB GO/pathway/word enrichment —
the exact wire format the journeys hit. The journeys run this against live
WDK; here we pin the transformation deterministically.
"""

from __future__ import annotations

import pytest

from pathfinder.platform.types import JSONObject
from pathfinder.services.enrichment.html import parse_result_genes_html
from pathfinder.services.enrichment.parser import (
    infer_enrichment_type,
    parse_enrichment_from_raw,
    parse_enrichment_response,
    parse_enrichment_terms,
)


def _go_row() -> JSONObject:
    return {
        "goId": "GO:0004672",
        "goTerm": "protein kinase activity",
        "bgdGenes": "120",
        "resultGenes": (
            "<a href='?param.ds_gene_ids.idList="
            "PF3D7_0100100,PF3D7_0200200,PF3D7_0300300&autoRun=1'>3</a>"
        ),
        "percentInResult": "12.5",
        "foldEnrich": "3.48",
        "oddsRatio": "4.12",
        "pValue": "0.0001",
        "benjamini": "0.002",
        "bonferroni": "0.005",
    }


def test_parse_go_rows_yields_real_terms() -> None:
    [term] = parse_enrichment_terms([_go_row()], "go_function")
    assert term.term_id == "GO:0004672"
    assert term.term_name == "protein kinase activity"
    assert term.gene_count == 3
    assert term.genes == ["PF3D7_0100100", "PF3D7_0200200", "PF3D7_0300300"]
    assert term.background_count == 120
    assert term.fold_enrichment == pytest.approx(3.48)
    assert term.odds_ratio == pytest.approx(4.12)
    assert term.p_value == pytest.approx(0.0001)
    assert term.fdr == pytest.approx(0.002)
    assert term.bonferroni == pytest.approx(0.005)


def test_parse_pathway_rows_uses_pathway_id_and_name() -> None:
    row: JSONObject = {
        "pathwayId": "kegg_pfa00010",
        "pathwayName": "Glycolysis / Gluconeogenesis",
        "bgdGenes": "60",
        "resultGenes": "<a href='?param.ds_gene_ids.idList=PF3D7_0915000&autoRun=1'>1</a>",
        "foldEnrich": "2.10",
        "oddsRatio": "2.5",
        "pValue": "0.01",
        "benjamini": "0.04",
        "bonferroni": "0.09",
    }
    [term] = parse_enrichment_terms([row], "pathway")
    assert term.term_id == "kegg_pfa00010"
    assert term.term_name == "Glycolysis / Gluconeogenesis"
    assert term.gene_count == 1
    assert term.genes == ["PF3D7_0915000"]
    assert term.p_value == pytest.approx(0.01)


def test_parse_word_rows_map_word_to_id_and_descrip_to_name() -> None:
    # WDK Java field ``_descrip`` serializes to JSON key ``pathwayName``.
    row: JSONObject = {
        "word": "kinase",
        "pathwayName": "protein kinase, putative",
        "bgdGenes": "200",
        "resultGenes": "42",
        "foldEnrich": "1.8",
        "pValue": "0.005",
        "benjamini": "0.02",
        "bonferroni": "0.06",
    }
    [term] = parse_enrichment_terms([row], "word")
    assert term.term_id == "kinase"
    assert term.term_name == "protein kinase, putative"
    # Plain-count resultGenes (no HTML link) → count, no IDs.
    assert term.gene_count == 42
    assert term.genes == []


def test_result_genes_html_extracts_count_and_ids() -> None:
    count, genes = parse_result_genes_html(
        "<a href='?param.ds_gene_ids.idList=PF3D7_0100100,PF3D7_0200200&autoRun=1'>2</a>"
    )
    assert count == 2
    assert genes == ["PF3D7_0100100", "PF3D7_0200200"]


def test_parse_from_raw_infers_type_and_parses_terms_end_to_end() -> None:
    result: JSONObject = {
        "resultData": [
            {
                "pathwayId": "kegg_pfa03030",
                "pathwayName": "DNA replication",
                "bgdGenes": "35",
                "resultGenes": "<a href='?param.ds_gene_ids.idList=PF3D7_1361900&autoRun=1'>1</a>",
                "foldEnrich": "5.0",
                "pValue": "0.0008",
                "benjamini": "0.01",
                "bonferroni": "0.03",
            }
        ],
        "downloadPath": "/a/b",
        "pvalueCutoff": "0.05",
    }
    res = parse_enrichment_from_raw("pathway-enrichment", {}, result)
    assert res.analysis_type == "pathway"
    assert [t.term_id for t in res.terms] == ["kegg_pfa03030"]
    assert res.terms[0].term_name == "DNA replication"


def test_parse_from_raw_derives_total_genes_analyzed_from_percent() -> None:
    result: JSONObject = {"resultData": [_go_row()], "pvalueCutoff": "0.05"}
    res = parse_enrichment_from_raw("go-enrichment", {}, result)
    assert res.total_genes_analyzed == 24


def test_infer_go_ontology_from_param() -> None:
    # WDK vocab params arrive as JSON array strings.
    assert (
        infer_enrichment_type(
            "go-enrichment",
            {"goAssociationsOntologies": '["Molecular Function"]'},
            {},
        )
        == "go_function"
    )
    assert (
        infer_enrichment_type(
            "go-enrichment",
            {"goAssociationsOntologies": '["Cellular Component"]'},
            {},
        )
        == "go_component"
    )


def test_malformed_row_missing_go_id_is_skipped() -> None:
    rows: list[JSONObject] = [{"goTerm": "no id here", "pValue": "0.1"}, _go_row()]
    terms = parse_enrichment_terms(rows, "go_process")
    # Only the well-formed row survives.
    assert [t.term_id for t in terms] == ["GO:0004672"]


def test_infinity_pvalue_clamped_to_zero() -> None:
    row: JSONObject = {**_go_row(), "pValue": "Infinity", "foldEnrich": "Infinity"}
    [term] = parse_enrichment_terms([row], "go_process")
    assert term.p_value == 0.0
    assert term.fold_enrichment == 0.0


def test_non_dict_result_yields_empty_envelope() -> None:
    assert parse_enrichment_response("not a dict").result_data == []
    assert parse_enrichment_response(None).result_data == []
