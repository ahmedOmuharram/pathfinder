"""Tests for experiment analysis AI helper functions."""

from veupath_chatbot.integrations.veupathdb.wdk_models import WDKRecordInstance
from veupath_chatbot.services.experiment.ai_analysis_helpers import (
    classify_gene,
    record_matches,
)
from veupath_chatbot.services.wdk.helpers import extract_pk


class TestExtractPk:
    def test_standard_wdk_record(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id", "value": "PF3D7_0100100"}])
        assert extract_pk(record) == "PF3D7_0100100"

    def test_strips_whitespace(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id", "value": "  PF3D7_0100100  "}])
        assert extract_pk(record) == "PF3D7_0100100"

    def test_empty_id_list(self) -> None:
        record = WDKRecordInstance(id=[])
        assert extract_pk(record) is None

    def test_missing_value_key(self) -> None:
        record = WDKRecordInstance(id=[{"name": "source_id"}])
        assert extract_pk(record) is None

    def test_multiple_pk_columns(self) -> None:
        """Should return the first entry's value."""
        record = WDKRecordInstance(
            id=[
                {"name": "source_id", "value": "PF3D7_0100100"},
                {"name": "project_id", "value": "PlasmoDB"},
            ]
        )
        assert extract_pk(record) == "PF3D7_0100100"


class TestClassifyGene:
    def test_true_positive(self) -> None:
        assert classify_gene("g1", {"g1"}, set(), set(), set()) == "TP"

    def test_false_positive(self) -> None:
        assert classify_gene("g1", set(), {"g1"}, set(), set()) == "FP"

    def test_false_negative(self) -> None:
        assert classify_gene("g1", set(), set(), {"g1"}, set()) == "FN"

    def test_true_negative(self) -> None:
        assert classify_gene("g1", set(), set(), set(), {"g1"}) == "TN"

    def test_not_in_any_set(self) -> None:
        assert classify_gene("g1", set(), set(), set(), set()) is None

    def test_none_gene_id(self) -> None:
        assert classify_gene(None, {"g1"}, set(), set(), set()) is None

    def test_empty_gene_id(self) -> None:
        assert classify_gene("", {"g1"}, set(), set(), set()) is None

    def test_priority_tp_over_fp(self) -> None:
        """If a gene is in multiple sets, TP takes priority."""
        assert classify_gene("g1", {"g1"}, {"g1"}, set(), set()) == "TP"


class TestRecordMatches:
    def test_matches_specific_attribute(self) -> None:
        attrs = {"product": "Protein kinase", "organism": "P. falciparum"}
        assert record_matches(attrs, "kinase", "product") is True
        assert record_matches(attrs, "kinase", "organism") is False

    def test_matches_any_attribute(self) -> None:
        attrs = {"product": "Protein kinase", "organism": "P. falciparum"}
        assert record_matches(attrs, "kinase", None) is True
        assert record_matches(attrs, "falciparum", None) is True

    def test_case_insensitive(self) -> None:
        attrs = {"product": "Protein KINASE"}
        assert record_matches(attrs, "kinase", "product") is True

    def test_no_match(self) -> None:
        attrs = {"product": "Ribosome", "organism": "P. vivax"}
        assert record_matches(attrs, "kinase", None) is False

    def test_non_string_values_skipped(self) -> None:
        attrs = {"count": 42, "product": "kinase"}
        assert record_matches(attrs, "kinase", None) is True
        assert record_matches(attrs, "42", None) is False

    def test_empty_attrs(self) -> None:
        assert record_matches({}, "kinase", None) is False
        assert record_matches({}, "kinase", "product") is False
