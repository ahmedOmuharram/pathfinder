"""Tests for shared AST parsing helpers (filters, analyses, reports, colocation)."""

from veupath_chatbot.domain.strategy.ast import (
    StepAnalysis,
    StepFilter,
    StepReport,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams


class TestParseFilters:
    def test_empty_list(self) -> None:
        assert StepFilter.from_list([]) == []

    def test_none_input(self) -> None:
        assert StepFilter.from_list(None) == []

    def test_non_list_input(self) -> None:
        assert StepFilter.from_list("not a list") == []

    def test_valid_filter(self) -> None:
        result = StepFilter.from_list([{"name": "ranked", "value": 5}])
        assert len(result) == 1
        assert result[0].name == "ranked"
        assert result[0].value == 5
        assert result[0].disabled is False

    def test_disabled_filter(self) -> None:
        result = StepFilter.from_list([{"name": "f1", "value": "x", "disabled": True}])
        assert result[0].disabled is True

    def test_skips_missing_name(self) -> None:
        result = StepFilter.from_list([{"value": 5}])
        assert result == []

    def test_skips_non_dict_items(self) -> None:
        result = StepFilter.from_list([42, "bad", {"name": "ok", "value": 1}])
        assert len(result) == 1
        assert result[0].name == "ok"


class TestParseAnalyses:
    def test_empty_list(self) -> None:
        assert StepAnalysis.from_list([]) == []

    def test_none_input(self) -> None:
        assert StepAnalysis.from_list(None) == []

    def test_valid_analysis(self) -> None:
        result = StepAnalysis.from_list(
            [
                {
                    "analysisType": "enrichment",
                    "parameters": {"dataset": "GO"},
                    "customName": "GO enrichment",
                }
            ]
        )
        assert len(result) == 1
        assert result[0].analysis_type == "enrichment"
        assert result[0].parameters == {"dataset": "GO"}
        assert result[0].custom_name == "GO enrichment"

    def test_snake_case_keys(self) -> None:
        result = StepAnalysis.from_list(
            [
                {
                    "analysis_type": "pathway",
                    "custom_name": "KEGG",
                }
            ]
        )
        assert len(result) == 1
        assert result[0].analysis_type == "pathway"
        assert result[0].custom_name == "KEGG"

    def test_skips_missing_analysis_type(self) -> None:
        result = StepAnalysis.from_list([{"parameters": {}}])
        assert result == []

    def test_defaults_parameters_to_empty_dict(self) -> None:
        result = StepAnalysis.from_list([{"analysisType": "word"}])
        assert result[0].parameters == {}


class TestParseReports:
    def test_empty_list(self) -> None:
        assert StepReport.from_list([]) == []

    def test_none_input(self) -> None:
        assert StepReport.from_list(None) == []

    def test_valid_report(self) -> None:
        result = StepReport.from_list(
            [
                {
                    "reportName": "fullRecord",
                    "config": {"format": "json"},
                }
            ]
        )
        assert len(result) == 1
        assert result[0].report_name == "fullRecord"
        assert result[0].config == {"format": "json"}

    def test_snake_case_key(self) -> None:
        result = StepReport.from_list([{"report_name": "tabular"}])
        assert result[0].report_name == "tabular"

    def test_defaults_report_name_to_standard(self) -> None:
        result = StepReport.from_list([{}])
        assert len(result) == 1
        assert result[0].report_name == "standard"

    def test_defaults_config_to_empty_dict(self) -> None:
        result = StepReport.from_list([{"reportName": "standard"}])
        assert result[0].config == {}


class TestParseColocationParams:
    def test_none_input(self) -> None:
        assert ColocationParams.from_json(None) is None

    def test_non_dict_input(self) -> None:
        assert ColocationParams.from_json("not a dict") is None

    def test_valid_params(self) -> None:
        result = ColocationParams.from_json(
            {
                "upstream": 1000,
                "downstream": 500,
                "strand": "same",
            }
        )
        assert result is not None
        assert result.upstream == 1000
        assert result.downstream == 500
        assert result.strand == "same"

    def test_defaults(self) -> None:
        result = ColocationParams.from_json({})
        assert result is not None
        assert result.upstream == 0
        assert result.downstream == 0
        assert result.strand == "both"

    def test_float_values_coerced_to_int(self) -> None:
        result = ColocationParams.from_json({"upstream": 1000.5, "downstream": 200.0})
        assert result is not None
        assert result.upstream == 1000
        assert result.downstream == 200

    def test_invalid_strand_defaults_to_both(self) -> None:
        result = ColocationParams.from_json({"strand": "bogus"})
        assert result is not None
        assert result.strand == "both"

    def test_opposite_strand(self) -> None:
        result = ColocationParams.from_json({"strand": "opposite"})
        assert result is not None
        assert result.strand == "opposite"
