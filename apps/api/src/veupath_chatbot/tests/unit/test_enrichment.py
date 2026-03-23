"""Tests for enrichment analysis helpers.

Verifies parameter names match VEuPathDB WDK step analysis plugins
(``stepAnalysisPlugins.xml`` / ``GoEnrichmentPlugin.java``).
"""

import pytest

from veupath_chatbot.services.enrichment.html import parse_result_genes_html
from veupath_chatbot.services.enrichment.params import (
    encode_vocab_params,
    encode_vocab_value,
    extract_default_params,
    extract_vocab_values,
)
from veupath_chatbot.services.enrichment.parser import (
    ANALYSIS_TYPE_MAP,
    GO_ONTOLOGY_MAP,
    infer_enrichment_type,
    is_enrichment_analysis,
    parse_enrichment_from_raw,
    parse_enrichment_terms,
    upsert_enrichment_result,
)
from veupath_chatbot.services.enrichment.types import EnrichmentResult
from veupath_chatbot.tests.fixtures.wdk_responses import (
    go_enrichment_form_response,
    pathway_enrichment_form_response,
)


class TestAnalysisTypeMaps:
    """Verify constants match WDK stepAnalysisPlugins.xml plugin names."""

    def test_go_types_map_to_go_enrichment(self) -> None:
        for key in ("go_function", "go_component", "go_process"):
            assert ANALYSIS_TYPE_MAP[key] == "go-enrichment"

    def test_pathway_maps_to_pathway_enrichment(self) -> None:
        assert ANALYSIS_TYPE_MAP["pathway"] == "pathway-enrichment"

    def test_word_maps_to_word_enrichment(self) -> None:
        assert ANALYSIS_TYPE_MAP["word"] == "word-enrichment"

    def test_go_ontology_values_match_wdk(self) -> None:
        assert GO_ONTOLOGY_MAP["go_function"] == "Molecular Function"
        assert GO_ONTOLOGY_MAP["go_component"] == "Cellular Component"
        assert GO_ONTOLOGY_MAP["go_process"] == "Biological Process"

    def test_go_ontology_keys_subset_of_analysis_map(self) -> None:
        assert set(GO_ONTOLOGY_MAP.keys()).issubset(set(ANALYSIS_TYPE_MAP.keys()))


class TestEncodeVocabParams:
    """encode_vocab_params encodes vocabulary params as JSON arrays.

    WDK ``AbstractEnumParam.convertToTerms()`` does
    ``new JSONArray(stableValue)`` — vocab param values MUST be
    JSON-encoded arrays.  Only ``single-pick-vocabulary`` and
    ``multi-pick-vocabulary`` types (from ``EnumParamFormatter.getParamType()``)
    need this encoding.  All other types (``number``, ``string``, ``filter``,
    ``input-step``, ``input-dataset``, etc.) are left as-is.
    """

    def test_encodes_user_params_after_merge(self) -> None:
        """User-supplied plain strings must be encoded after merge.

        This is the critical bug: ``_merge_analysis_params`` was doing
        ``{**defaults, **user_params}``, letting plain-string user params
        override properly-encoded defaults.  ``encode_vocab_params``
        re-encodes all vocab params using the form metadata.
        """
        form = pathway_enrichment_form_response()
        # Simulate what happens: user sends plain strings from frontend
        merged = {
            "organism": "Plasmodium falciparum 3D7",  # plain string (from user)
            "pathwaysSources": '["KEGG","MetaCyc"]',  # already JSON array
            "pValueCutoff": "0.05",
            "exact_match_only": "Yes",  # plain string (from user)
            "exclude_incomplete_ec": "No",  # plain string (from user)
        }
        result = encode_vocab_params(merged, form)

        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["exact_match_only"] == '["Yes"]'
        assert result["exclude_incomplete_ec"] == '["No"]'
        assert result["pathwaysSources"] == '["KEGG","MetaCyc"]'  # unchanged
        assert result["pValueCutoff"] == "0.05"  # number — unchanged

    def test_does_not_double_encode(self) -> None:
        """Values already encoded as JSON arrays are left alone."""
        form = pathway_enrichment_form_response()
        merged = {
            "organism": '["Plasmodium falciparum 3D7"]',  # already encoded
            "exact_match_only": '["Yes"]',
            "pValueCutoff": "0.05",
        }
        result = encode_vocab_params(merged, form)
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["exact_match_only"] == '["Yes"]'

    def test_handles_missing_form_metadata(self) -> None:
        """When form metadata is empty/invalid, params are returned as-is."""
        merged = {"organism": "Plasmodium falciparum 3D7"}
        assert encode_vocab_params(merged, {}) == merged
        assert encode_vocab_params(merged, None) == merged

    def test_handles_params_not_in_form(self) -> None:
        """Params not listed in form metadata are left untouched."""
        form = pathway_enrichment_form_response()
        merged = {
            "organism": "Plasmodium falciparum 3D7",
            "unknownParam": "some value",
        }
        result = encode_vocab_params(merged, form)
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["unknownParam"] == "some value"

    def test_multi_pick_vocab_encoded(self) -> None:
        form_meta = {
            "searchData": {
                "parameters": [
                    {"name": "codes", "type": "multi-pick-vocabulary"},
                ],
            },
        }
        params = {"codes": "IDA"}
        result = encode_vocab_params(params, form_meta)
        assert result["codes"] == '["IDA"]'

    def test_non_string_value_not_encoded(self) -> None:
        """Only string values get vocabulary encoding."""
        form_meta = {
            "searchData": {
                "parameters": [
                    {"name": "organism", "type": "single-pick-vocabulary"},
                ],
            },
        }
        params = {"organism": ["Pf3D7"]}
        result = encode_vocab_params(params, form_meta)
        assert result["organism"] == ["Pf3D7"]


class TestExtractDefaultParams:
    """extract_default_params extracts name/initialDisplayValue from WDK form metadata.

    WDK's ``ParamFormatter.java`` uses ``initialDisplayValue`` as the
    stable default value field (via ``JsonKeys.INITIAL_DISPLAY_VALUE``).
    """

    def test_extracts_and_encodes_enum_params(self) -> None:
        """Single-pick enum/vocab params are wrapped in JSON arrays.

        WDK pathway-enrichment ``organism`` has ``initialDisplayValue``
        of ``"Plasmodium falciparum 3D7"`` (plain string), but the plugin
        does ``AbstractEnumParam.convertToTerms(params.get("organism"))``
        which calls ``new JSONArray(stableValue)`` — requires JSON array.
        """
        form = pathway_enrichment_form_response()
        result = extract_default_params(form)

        # Enum/vocab params must be JSON arrays
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'
        assert result["exact_match_only"] == '["Yes"]'
        assert result["exclude_incomplete_ec"] == '["No"]'

        # Multi-pick enum already comes as JSON array — must stay as-is
        assert result["pathwaysSources"] == '["KEGG","MetaCyc"]'

        # NumberParam stays as plain string
        assert result["pValueCutoff"] == "0.05"

    def test_extracts_go_enrichment_params(self) -> None:
        form = go_enrichment_form_response()
        result = extract_default_params(form)

        assert result["goAssociationsOntologies"] == '["Biological Process"]'
        assert result["goEvidenceCodes"] == '["Computed","Curated"]'
        assert result["pValueCutoff"] == "0.05"
        assert result["organism"] == '["Plasmodium falciparum 3D7"]'

    def test_extracts_from_valid_form(self) -> None:
        """Legacy form without type info: values are kept as-is."""
        form = {
            "parameters": [
                {
                    "name": "goAssociationsOntologies",
                    "initialDisplayValue": "Biological Process",
                },
                {"name": "pValueCutoff", "initialDisplayValue": "0.05"},
                {
                    "name": "organism",
                    "initialDisplayValue": "Plasmodium falciparum 3D7",
                },
            ]
        }
        result = extract_default_params(form)
        assert result == {
            "goAssociationsOntologies": "Biological Process",
            "pValueCutoff": "0.05",
            "organism": "Plasmodium falciparum 3D7",
        }

    def test_skips_none_initial_display_value(self) -> None:
        """Parameters with None initialDisplayValue are omitted (WDK rejects empty)."""
        form = {"parameters": [{"name": "pValueCutoff", "initialDisplayValue": None}]}
        result = extract_default_params(form)
        assert result == {}

    def test_skips_missing_initial_display_value(self) -> None:
        """Parameters without initialDisplayValue are omitted."""
        form = {"parameters": [{"name": "pValueCutoff"}]}
        result = extract_default_params(form)
        assert result == {}

    def test_skips_invalid_entries(self) -> None:
        form = {
            "parameters": [
                {"name": "valid", "initialDisplayValue": "x"},
                {"name": "", "initialDisplayValue": "y"},
                {"name": None, "initialDisplayValue": "z"},
                {"initialDisplayValue": "no name"},
                "not a dict",
            ]
        }
        result = extract_default_params(form)
        assert result == {"valid": "x"}

    def test_handles_no_parameters_key(self) -> None:
        assert extract_default_params({}) == {}

    def test_handles_non_list_parameters(self) -> None:
        assert extract_default_params({"parameters": "bad"}) == {}

    def test_handles_non_dict_input(self) -> None:
        assert extract_default_params(None) == {}
        assert extract_default_params([]) == {}
        assert extract_default_params("string") == {}

    def test_numeric_initial_display_value(self) -> None:
        """initialDisplayValue as a number is converted to string."""
        form = {
            "parameters": [
                {"name": "cutoff", "initialDisplayValue": 0.05},
            ]
        }
        result = extract_default_params(form)
        assert result["cutoff"] == "0.05"

    def test_boolean_initial_display_value(self) -> None:
        """initialDisplayValue as a boolean is converted to string."""
        form = {
            "parameters": [
                {"name": "flag", "initialDisplayValue": True},
            ]
        }
        result = extract_default_params(form)
        assert result["flag"] == "True"


class TestExtractVocabValues:
    """extract_vocab_values extracts allowed values from WDK param vocabulary."""

    def test_extracts_ontology_values_from_go_form(self) -> None:
        """Real WDK GO enrichment form has vocabulary triples: [value, display, null]."""
        form = {
            "searchData": {
                "parameters": [
                    {
                        "name": "goAssociationsOntologies",
                        "type": "single-pick-vocabulary",
                        "vocabulary": [
                            ["Cellular Component", "Cellular Component", None],
                            ["Molecular Function", "Molecular Function", None],
                        ],
                    },
                ]
            }
        }
        values = extract_vocab_values(form, "goAssociationsOntologies")
        assert values == ["Cellular Component", "Molecular Function"]

    def test_extracts_all_three_ontologies(self) -> None:
        """PlasmoDB has all 3 GO ontologies available."""
        form = {
            "searchData": {
                "parameters": [
                    {
                        "name": "goAssociationsOntologies",
                        "type": "single-pick-vocabulary",
                        "vocabulary": [
                            ["Biological Process", "Biological Process", None],
                            ["Cellular Component", "Cellular Component", None],
                            ["Molecular Function", "Molecular Function", None],
                        ],
                    },
                ]
            }
        }
        values = extract_vocab_values(form, "goAssociationsOntologies")
        assert "Biological Process" in values
        assert "Cellular Component" in values
        assert "Molecular Function" in values

    def test_returns_empty_for_missing_param(self) -> None:
        form = {"searchData": {"parameters": [{"name": "other", "vocabulary": []}]}}
        assert extract_vocab_values(form, "goAssociationsOntologies") == []

    def test_returns_empty_for_no_vocabulary(self) -> None:
        form = {"searchData": {"parameters": [{"name": "goAssociationsOntologies"}]}}
        assert extract_vocab_values(form, "goAssociationsOntologies") == []

    def test_returns_empty_for_none_input(self) -> None:
        assert extract_vocab_values(None, "anything") == []

    def test_returns_empty_for_empty_dict(self) -> None:
        assert extract_vocab_values({}, "anything") == []

    def test_handles_form_without_search_data_wrapper(self) -> None:
        """Form metadata may or may not have the searchData wrapper."""
        form = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "single-pick-vocabulary",
                    "vocabulary": [
                        ["Plasmodium falciparum 3D7", "P. falciparum 3D7", None],
                    ],
                },
            ]
        }
        values = extract_vocab_values(form, "organism")
        assert values == ["Plasmodium falciparum 3D7"]


class TestParseEnrichmentTerms:
    """parse_enrichment_terms handles both WDK row formats."""

    def test_parses_standard_wdk_rows(self) -> None:
        """WDK GO enrichment: all camelCase keys, all string values, HTML resultGenes."""
        rows = [
            {
                "goId": "GO:0003735",
                "goTerm": "structural constituent of ribosome",
                "bgdGenes": "100",
                "resultGenes": "<a href='?idList=PF3D7_0100100,PF3D7_0831900&autoRun=1'>42</a>",
                "foldEnrich": "3.14",
                "oddsRatio": "2.5",
                "pValue": "0.001",
                "benjamini": "0.01",
                "bonferroni": "0.05",
            }
        ]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert len(terms) == 1
        t = terms[0]
        assert t.term_id == "GO:0003735"
        assert t.term_name == "structural constituent of ribosome"
        assert t.gene_count == 42
        assert t.background_count == 100
        assert t.fold_enrichment == pytest.approx(3.14)
        assert t.odds_ratio == pytest.approx(2.5)
        assert t.p_value == pytest.approx(0.001)
        assert t.fdr == pytest.approx(0.01)
        assert t.bonferroni == pytest.approx(0.05)
        assert t.genes == ["PF3D7_0100100", "PF3D7_0831900"]

    def test_handles_empty_list(self) -> None:
        assert parse_enrichment_terms([], analysis_type="go_process") == []

    def test_skips_non_dict_entries(self) -> None:
        rows: list = [{"goId": "GO:1", "goTerm": "x"}, "bad", None]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert len(terms) == 1

    def test_parses_wdk_go_enrichment_rows(self) -> None:
        """WDK GO enrichment uses goId, goTerm, resultGenes (HTML), bgdGenes, foldEnrich."""
        rows = [
            {
                "goId": "GO:0006260",
                "goTerm": "DNA replication",
                "resultGenes": "<a href='/a/app/search/transcript/GeneByLocusTag?param.ds_gene_ids.idList=PF3D7_0111300,PF3D7_0215800,&autoRun=1'>2</a>",
                "bgdGenes": "46",
                "foldEnrich": "3.48",
                "oddsRatio": "9.46",
                "pValue": "3.40e-13",
                "benjamini": "4.58e-10",
                "bonferroni": "4.58e-10",
                "percentInResult": "69.6",
            }
        ]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert len(terms) == 1
        t = terms[0]
        assert t.term_id == "GO:0006260"
        assert t.term_name == "DNA replication"
        assert t.gene_count == 2
        assert t.background_count == 46
        assert t.fold_enrichment == pytest.approx(3.48)
        assert t.odds_ratio == pytest.approx(9.46)
        assert t.p_value == pytest.approx(3.40e-13)
        assert t.fdr == pytest.approx(4.58e-10)
        assert t.bonferroni == pytest.approx(4.58e-10)
        assert t.genes == ["PF3D7_0111300", "PF3D7_0215800"]

    def test_infinity_odds_ratio_becomes_zero(self) -> None:
        """WDK returns 'Infinity' for oddsRatio when denominator is zero."""
        rows = [
            {
                "goId": "GO:0009060",
                "goTerm": "aerobic respiration",
                "resultGenes": "<a href='?idList=G1,&autoRun=1'>1</a>",
                "bgdGenes": "0",
                "foldEnrich": "Infinity",
                "oddsRatio": "Infinity",
                "pValue": "0.001",
                "benjamini": "0.01",
                "bonferroni": "0.05",
            }
        ]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert len(terms) == 1
        t = terms[0]
        assert t.fold_enrichment == 0.0
        assert t.odds_ratio == 0.0

    def test_parses_word_enrichment_rows(self) -> None:
        """WDK Word enrichment uses 'word' as ID and 'pathwayName' as description."""
        rows = [
            {
                "word": "kinase",
                "pathwayName": "Protein kinase activity",
                "bgdGenes": "300",
                "resultGenes": "<a href='?idList=G1,G2,&autoRun=1'>2</a>",
                "foldEnrich": "4.2",
                "oddsRatio": "3.1",
                "pValue": "0.003",
                "benjamini": "0.02",
                "bonferroni": "0.04",
            }
        ]
        terms = parse_enrichment_terms(rows, analysis_type="word")
        assert len(terms) == 1
        t = terms[0]
        assert t.term_id == "kinase"
        assert t.term_name == "Protein kinase activity"
        assert t.gene_count == 2
        assert t.background_count == 300
        assert t.fold_enrichment == pytest.approx(4.2)
        assert t.genes == ["G1", "G2"]

    def test_parses_word_enrichment_no_pathway_name(self) -> None:
        """Word enrichment with no 'pathwayName' uses empty string for name."""
        rows = [
            {
                "word": "ribosome",
                "bgdGenes": "50",
                "resultGenes": "<a href='?idList=G1,&autoRun=1'>1</a>",
                "foldEnrich": "2.0",
                "oddsRatio": "1.5",
                "pValue": "0.05",
                "benjamini": "0.1",
                "bonferroni": "0.2",
            }
        ]
        terms = parse_enrichment_terms(rows, analysis_type="word")
        assert len(terms) == 1
        assert terms[0].term_id == "ribosome"
        assert terms[0].term_name == ""

    def test_parses_pathway_enrichment_rows(self) -> None:
        """Pathway enrichment uses pathwayId and pathwayName."""
        rows = [
            {
                "pathwayId": "ec01100",
                "pathwayName": "Metabolic pathways",
                "bgdGenes": "200",
                "resultGenes": "<a href='?idList=G1,G2,G3,&autoRun=1'>3</a>",
                "foldEnrich": "2.5",
                "oddsRatio": "1.8",
                "pValue": "0.01",
                "benjamini": "0.05",
                "bonferroni": "0.1",
            }
        ]
        terms = parse_enrichment_terms(rows, analysis_type="pathway")
        assert len(terms) == 1
        assert terms[0].term_id == "ec01100"
        assert terms[0].term_name == "Metabolic pathways"
        assert terms[0].gene_count == 3
        assert terms[0].genes == ["G1", "G2", "G3"]


class TestParseResultGenesHtml:
    """parse_result_genes_html extracts count and gene IDs from WDK HTML links."""

    def test_extracts_count_and_genes(self) -> None:
        html = "<a href='/search?param.ds_gene_ids.idList=GENE_A,GENE_B,GENE_C,&autoRun=1'>3</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 3
        assert genes == ["GENE_A", "GENE_B", "GENE_C"]

    def test_handles_no_trailing_comma(self) -> None:
        html = "<a href='?idList=G1,G2&autoRun=1'>2</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 2
        assert genes == ["G1", "G2"]

    def test_handles_empty_html(self) -> None:
        count, genes = parse_result_genes_html("")
        assert count == 0
        assert genes == []

    def test_handles_no_idlist(self) -> None:
        html = "<a href='/search'>5</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 5
        assert genes == []

    def test_multiple_links_takes_first_count(self) -> None:
        html = "<a href='?idList=G1&x'>5</a> more text <a href='?idList=G2&x'>3</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 5
        assert genes == ["G1"]

    def test_count_zero_in_link(self) -> None:
        html = "<a href='?idList=&autoRun=1'>0</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 0
        assert genes == []

    def test_genes_with_whitespace(self) -> None:
        html = "<a href='?idList= G1 , G2 ,&autoRun=1'>2</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 2
        assert genes == ["G1", "G2"]

    def test_single_gene_no_comma(self) -> None:
        html = "<a href='?idList=PF3D7_0100100&autoRun=1'>1</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 1
        assert genes == ["PF3D7_0100100"]

    def test_malformed_html_no_href(self) -> None:
        html = "<span>42</span>"
        count, genes = parse_result_genes_html(html)
        assert count == 42
        assert genes == []

    def test_idlist_with_special_chars_in_gene_ids(self) -> None:
        """Gene IDs can contain dots, underscores, etc."""
        html = "<a href='?idList=TGME49_123.1,TGGT1_456.2&autoRun=1'>2</a>"
        count, genes = parse_result_genes_html(html)
        assert count == 2
        assert genes == ["TGME49_123.1", "TGGT1_456.2"]

    def test_plain_number_no_tags(self) -> None:
        """If the HTML is just a number without tags, no match."""
        count, genes = parse_result_genes_html("42")
        assert count == 0
        assert genes == []


class TestInferEnrichmentType:
    """infer_enrichment_type resolves WDK analysis names to EnrichmentAnalysisType."""

    def test_go_enrichment_from_params(self) -> None:
        assert (
            infer_enrichment_type(
                "go-enrichment",
                {"goAssociationsOntologies": "Molecular Function"},
                {},
            )
            == "go_function"
        )

    def test_go_enrichment_from_result_ontologies(self) -> None:
        assert (
            infer_enrichment_type(
                "go-enrichment",
                {},
                {"goOntologies": ["Cellular Component"]},
            )
            == "go_component"
        )

    def test_go_enrichment_defaults_to_go_process(self) -> None:
        assert infer_enrichment_type("go-enrichment", {}, {}) == "go_process"

    def test_pathway_enrichment(self) -> None:
        assert infer_enrichment_type("pathway-enrichment", {}, {}) == "pathway"

    def test_word_enrichment(self) -> None:
        assert infer_enrichment_type("word-enrichment", {}, {}) == "word"

    def test_go_enrichment_with_json_array_ontology(self) -> None:
        """WDK vocab params arrive as JSON array strings like '["Molecular Function"]'."""
        result = infer_enrichment_type(
            "go-enrichment",
            {"goAssociationsOntologies": '["Molecular Function"]'},
            {},
        )
        assert result == "go_function"

    def test_go_enrichment_prefers_params_over_result(self) -> None:
        """When params has ontology, result ontology is ignored."""
        result = infer_enrichment_type(
            "go-enrichment",
            {"goAssociationsOntologies": "Cellular Component"},
            {"goOntologies": ["Molecular Function"]},
        )
        assert result == "go_component"

    def test_go_enrichment_result_ontologies_empty_list(self) -> None:
        """Empty goOntologies list falls back to go_process."""
        result = infer_enrichment_type(
            "go-enrichment",
            {},
            {"goOntologies": []},
        )
        assert result == "go_process"

    def test_unknown_wdk_analysis_name(self) -> None:
        """Unknown analysis name falls back to go_process."""
        result = infer_enrichment_type("unknown-analysis", {}, {})
        assert result == "go_process"


class TestIsEnrichmentAnalysis:
    def test_recognizes_enrichment_names(self) -> None:
        assert is_enrichment_analysis("go-enrichment")
        assert is_enrichment_analysis("pathway-enrichment")
        assert is_enrichment_analysis("word-enrichment")

    def test_rejects_non_enrichment(self) -> None:
        assert not is_enrichment_analysis("word-cloud")
        assert not is_enrichment_analysis("some-other-analysis")

    def test_empty_string(self) -> None:
        assert is_enrichment_analysis("") is False

    def test_case_sensitive(self) -> None:
        """WDK analysis names are case-sensitive."""
        assert is_enrichment_analysis("GO-ENRICHMENT") is False
        assert is_enrichment_analysis("Go-Enrichment") is False


class TestParseEnrichmentFromRaw:
    """parse_enrichment_from_raw converts raw WDK JSON to EnrichmentResult."""

    def test_full_go_enrichment_result(self) -> None:
        raw = {
            "goOntologies": ["Biological Process"],
            "resultData": [
                {
                    "goId": "GO:0006260",
                    "goTerm": "DNA replication",
                    "resultGenes": "<a href='?idList=G1,G2,&autoRun=1'>2</a>",
                    "bgdGenes": "46",
                    "foldEnrich": "3.48",
                    "oddsRatio": "9.46",
                    "pValue": "3.40e-13",
                    "benjamini": "4.58e-10",
                    "bonferroni": "4.58e-10",
                },
            ],
        }
        er = parse_enrichment_from_raw("go-enrichment", {}, raw)
        assert er.analysis_type == "go_process"
        assert len(er.terms) == 1
        assert er.terms[0].term_id == "GO:0006260"
        assert er.terms[0].genes == ["G1", "G2"]


class TestUpsertEnrichmentResult:
    """upsert_enrichment_result replaces existing results of the same analysis_type."""

    def _make_result(self, analysis_type: str, n_terms: int = 1) -> EnrichmentResult:
        return EnrichmentResult(
            analysis_type=analysis_type,
            terms=[],
            total_genes_analyzed=n_terms,
            background_size=0,
        )

    def test_appends_new_type(self) -> None:
        results: list[EnrichmentResult] = []
        upsert_enrichment_result(results, self._make_result("go_process", 10))
        assert len(results) == 1
        assert results[0].total_genes_analyzed == 10

    def test_replaces_existing_type(self) -> None:
        results = [self._make_result("go_process", 5)]
        upsert_enrichment_result(results, self._make_result("go_process", 20))
        assert len(results) == 1
        assert results[0].total_genes_analyzed == 20

    def test_preserves_other_types(self) -> None:
        results = [
            self._make_result("go_process", 5),
            self._make_result("pathway", 10),
        ]
        upsert_enrichment_result(results, self._make_result("go_process", 20))
        assert len(results) == 2
        types = [r.analysis_type for r in results]
        assert types == ["go_process", "pathway"]
        assert results[0].total_genes_analyzed == 20
        assert results[1].total_genes_analyzed == 10

    def test_multiple_upserts(self) -> None:
        results: list[EnrichmentResult] = []
        upsert_enrichment_result(results, self._make_result("go_process"))
        upsert_enrichment_result(results, self._make_result("pathway"))
        upsert_enrichment_result(results, self._make_result("word"))
        upsert_enrichment_result(results, self._make_result("go_process", 99))
        upsert_enrichment_result(results, self._make_result("pathway", 88))
        assert len(results) == 3
        assert results[0].total_genes_analyzed == 99
        assert results[1].total_genes_analyzed == 88

    def test_upsert_replaces_correct_index(self) -> None:
        """When there are multiple types, only the matching one is replaced."""
        r1 = self._make_result("go_process", 1)
        r2 = self._make_result("pathway", 2)
        r3 = self._make_result("word", 3)
        results = [r1, r2, r3]
        upsert_enrichment_result(results, self._make_result("pathway", 99))
        assert len(results) == 3
        assert results[0].total_genes_analyzed == 1  # unchanged
        assert results[1].total_genes_analyzed == 99  # replaced
        assert results[2].total_genes_analyzed == 3  # unchanged


# ---------------------------------------------------------------------------
# Edge cases: parse_enrichment_terms
# ---------------------------------------------------------------------------


class TestParseEnrichmentTermsEdgeCases:
    """Edge cases for parse_enrichment_terms not covered by standard tests."""

    def test_all_fields_missing_produces_defaults(self) -> None:
        """GO row with required fields but no numeric fields -> defaults."""
        rows: list = [{"goId": "X", "goTerm": "Y"}]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert len(terms) == 1
        t = terms[0]
        assert t.term_id == "X"
        assert t.term_name == "Y"
        assert t.gene_count == 0
        assert t.background_count == 0
        assert t.fold_enrichment == 0.0
        assert t.odds_ratio == 0.0
        assert t.p_value == 1.0
        assert t.fdr == 1.0
        assert t.bonferroni == 1.0
        assert t.genes == []

    def test_result_genes_numeric_string_no_html(self) -> None:
        """resultGenes as plain numeric string -> gene_count parsed as int."""
        rows: list = [{"goId": "X", "goTerm": "Y", "resultGenes": "46"}]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert terms[0].gene_count == 46

    def test_result_genes_plain_text_no_html_returns_zero(self) -> None:
        """resultGenes as non-numeric text -> gene_count 0."""
        rows: list = [{"goId": "X", "goTerm": "Y", "resultGenes": "not_a_number"}]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert terms[0].gene_count == 0

    def test_nan_pvalue_handled(self) -> None:
        """NaN in p-value -> 0.0 (SafeFiniteFloat clamps nan)."""
        rows: list = [{"goId": "X", "goTerm": "Y", "pValue": "NaN"}]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert terms[0].p_value == 0.0

    def test_negative_infinity_fold_enrichment(self) -> None:
        """-Infinity fold enrichment -> 0.0 (SafeFiniteFloat clamps)."""
        rows: list = [{"goId": "X", "goTerm": "Y", "foldEnrich": "-Infinity"}]
        terms = parse_enrichment_terms(rows, analysis_type="go_process")
        assert terms[0].fold_enrichment == 0.0


# ---------------------------------------------------------------------------
# Edge cases: parse_enrichment_from_raw
# ---------------------------------------------------------------------------


class TestParseEnrichmentFromRawEdgeCases:
    """Edge cases for parse_enrichment_from_raw."""

    def test_non_dict_result(self) -> None:
        er = parse_enrichment_from_raw("go-enrichment", {}, None)
        assert er.total_genes_analyzed == 0
        assert er.background_size == 0
        assert er.terms == []

    def test_result_as_list(self) -> None:
        er = parse_enrichment_from_raw("go-enrichment", {}, [{"goId": "GO:1"}])
        assert er.total_genes_analyzed == 0
        assert er.terms == []

    def test_empty_dict_result(self) -> None:
        er = parse_enrichment_from_raw("pathway-enrichment", {}, {})
        assert er.analysis_type == "pathway"
        assert er.terms == []
        assert er.total_genes_analyzed == 0
        assert er.background_size == 0


# ---------------------------------------------------------------------------
# encode_vocab_value
# ---------------------------------------------------------------------------


class TestEncodeVocabValue:
    """encode_vocab_value wraps plain strings as JSON arrays."""

    def test_wraps_plain_string(self) -> None:
        assert encode_vocab_value("hello") == '["hello"]'

    def test_does_not_double_wrap_array(self) -> None:
        assert encode_vocab_value('["hello"]') == '["hello"]'

    def test_empty_string(self) -> None:
        assert encode_vocab_value("") == '[""]'

    def test_string_starting_with_bracket_but_not_json(self) -> None:
        result = encode_vocab_value("[not json")
        assert result == '["[not json"]'
