"""Tests for veupath_chatbot.services.experiment.classification."""

from veupath_chatbot.services.experiment.classification import classify_records


def _make_record(gene_id: str) -> dict[str, object]:
    """Build a minimal WDK-style record with a primary key."""
    return {"id": [{"name": "gene_source_id", "value": gene_id}], "attributes": {}}


# ---------------------------------------------------------------------------
# Basic classification
# ---------------------------------------------------------------------------


class TestClassifyRecords:
    """Tests for classify_records()."""

    def test_basic_tp(self) -> None:
        records = [_make_record("GENE_A")]
        result = classify_records(
            records, tp_ids={"GENE_A"}, fp_ids=set(), fn_ids=set(), tn_ids=set()
        )
        assert result[0]["_classification"] == "TP"

    def test_basic_fp(self) -> None:
        records = [_make_record("GENE_B")]
        result = classify_records(
            records, tp_ids=set(), fp_ids={"GENE_B"}, fn_ids=set(), tn_ids=set()
        )
        assert result[0]["_classification"] == "FP"

    def test_basic_fn(self) -> None:
        records = [_make_record("GENE_C")]
        result = classify_records(
            records, tp_ids=set(), fp_ids=set(), fn_ids={"GENE_C"}, tn_ids=set()
        )
        assert result[0]["_classification"] == "FN"

    def test_basic_tn(self) -> None:
        records = [_make_record("GENE_D")]
        result = classify_records(
            records, tp_ids=set(), fp_ids=set(), fn_ids=set(), tn_ids={"GENE_D"}
        )
        assert result[0]["_classification"] == "TN"

    def test_no_match_returns_none(self) -> None:
        records = [_make_record("UNKNOWN")]
        result = classify_records(
            records, tp_ids={"A"}, fp_ids={"B"}, fn_ids={"C"}, tn_ids={"D"}
        )
        assert result[0]["_classification"] is None

    def test_empty_records(self) -> None:
        result = classify_records(
            [], tp_ids=set(), fp_ids=set(), fn_ids=set(), tn_ids=set()
        )
        assert result == []

    def test_empty_gene_sets(self) -> None:
        records = [_make_record("GENE_X")]
        result = classify_records(
            records, tp_ids=set(), fp_ids=set(), fn_ids=set(), tn_ids=set()
        )
        assert result[0]["_classification"] is None

    # -----------------------------------------------------------------------
    # Transcript ID version stripping
    # -----------------------------------------------------------------------

    def test_transcript_version_stripping_tp(self) -> None:
        """'GENE.1' should match 'GENE' in tp_ids after version stripping."""
        records = [_make_record("PF3D7_0100100.1")]
        result = classify_records(
            records, tp_ids={"PF3D7_0100100"}, fp_ids=set(), fn_ids=set(), tn_ids=set()
        )
        assert result[0]["_classification"] == "TP"

    def test_transcript_version_stripping_fn(self) -> None:
        """Version stripping works for FN as well."""
        records = [_make_record("GENE_X.3")]
        result = classify_records(
            records, tp_ids=set(), fp_ids=set(), fn_ids={"GENE_X"}, tn_ids=set()
        )
        assert result[0]["_classification"] == "FN"

    def test_exact_match_takes_priority_over_stripped(self) -> None:
        """If the full ID 'GENE.1' is in fp_ids, that should match before stripping to 'GENE'."""
        records = [_make_record("GENE.1")]
        result = classify_records(
            records,
            tp_ids={"GENE"},
            fp_ids={"GENE.1"},
            fn_ids=set(),
            tn_ids=set(),
        )
        # Exact match "GENE.1" is checked first (FP), not stripped "GENE" (TP)
        assert result[0]["_classification"] == "FP"

    def test_no_dot_no_stripping(self) -> None:
        """ID without a dot should not be stripped."""
        records = [_make_record("GENE_NODOT")]
        result = classify_records(
            records, tp_ids=set(), fp_ids=set(), fn_ids=set(), tn_ids={"GENE_NODOT"}
        )
        assert result[0]["_classification"] == "TN"

    # -----------------------------------------------------------------------
    # Multiple records
    # -----------------------------------------------------------------------

    def test_multiple_records_mixed_classifications(self) -> None:
        records = [
            _make_record("A"),
            _make_record("B"),
            _make_record("C"),
            _make_record("UNKNOWN"),
        ]
        result = classify_records(
            records, tp_ids={"A"}, fp_ids={"B"}, fn_ids={"C"}, tn_ids=set()
        )
        assert len(result) == 4
        assert result[0]["_classification"] == "TP"
        assert result[1]["_classification"] == "FP"
        assert result[2]["_classification"] == "FN"
        assert result[3]["_classification"] is None

    def test_non_dict_records_are_skipped(self) -> None:
        """Non-dict entries in the records list should be silently skipped."""
        # Build a list with a non-dict element to test runtime robustness.
        records = [_make_record("A"), _make_record("B")]
        records.insert(1, "not a dict")  # intentionally wrong type at runtime
        result = classify_records(
            records,
            tp_ids={"A"},
            fp_ids={"B"},
            fn_ids=set(),
            tn_ids=set(),
        )
        assert len(result) == 2
        assert result[0]["_classification"] == "TP"
        assert result[1]["_classification"] == "FP"

    def test_preserves_original_record_fields(self) -> None:
        """Classification should not lose existing record fields."""
        records = [
            {
                "id": [{"name": "gene_source_id", "value": "G1"}],
                "attributes": {"score": 42},
            }
        ]
        result = classify_records(
            records, tp_ids={"G1"}, fp_ids=set(), fn_ids=set(), tn_ids=set()
        )
        assert result[0]["attributes"] == {"score": 42}
        assert result[0]["_classification"] == "TP"

    # -----------------------------------------------------------------------
    # Priority - TP > FP > FN > TN
    # -----------------------------------------------------------------------

    def test_priority_tp_over_fp(self) -> None:
        """If a gene ID is in both TP and FP, TP wins (checked first)."""
        records = [_make_record("BOTH")]
        result = classify_records(
            records, tp_ids={"BOTH"}, fp_ids={"BOTH"}, fn_ids=set(), tn_ids=set()
        )
        assert result[0]["_classification"] == "TP"
