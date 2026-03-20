"""Bug-hunting tests for helpers.py — safe_int, safe_float, extract_wdk_id, gene lists.

Covers:
- safe_int with strings, NaN, Infinity, booleans, None
- safe_float with NaN, Infinity, -Infinity, edge strings
- extract_wdk_id with various payload shapes
- coerce_step_id success/failure
- _extract_gene_list with missing sections, None entries
- _extract_id_set with various inputs
- _enrich_list with partial metadata
"""

import pytest

from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.services.experiment.helpers import (
    _enrich_list,
    _extract_gene_list,
    _extract_id_set,
    coerce_step_id,
    extract_wdk_id,
    safe_float,
    safe_int,
)
from veupath_chatbot.services.experiment.types import GeneInfo


class TestSafeInt:
    """safe_int converts various types to int safely."""

    def test_int_passthrough(self) -> None:
        assert safe_int(42) == 42

    def test_negative_int(self) -> None:
        assert safe_int(-5) == -5

    def test_zero(self) -> None:
        assert safe_int(0) == 0

    def test_float_truncated(self) -> None:
        assert safe_int(3.7) == 3

    def test_negative_float(self) -> None:
        assert safe_int(-2.9) == -2

    def test_string_numeric(self) -> None:
        """safe_int handles numeric strings (unlike _int in metrics.py)."""
        assert safe_int("42") == 42

    def test_string_float(self) -> None:
        """String with decimal should work via float() then int()."""
        assert safe_int("3.7") == 3

    def test_string_non_numeric(self) -> None:
        assert safe_int("hello") == 0

    def test_string_empty(self) -> None:
        assert safe_int("") == 0

    def test_none_returns_default(self) -> None:
        assert safe_int(None) == 0

    def test_custom_default(self) -> None:
        assert safe_int(None, -1) == -1

    def test_bool_true(self) -> None:
        """bool is a subclass of int."""
        assert safe_int(True) == 1

    def test_bool_false(self) -> None:
        assert safe_int(False) == 0

    def test_nan_string(self) -> None:
        """'NaN' string: float('NaN') -> NaN -> int(NaN) raises ValueError.

        The except clause catches ValueError. Returns default.
        """
        assert safe_int("NaN") == 0

    def test_infinity_string(self) -> None:
        """'Infinity': float('Infinity') -> inf -> int(inf) raises OverflowError.

        Caught by the except clause.
        """
        assert safe_int("Infinity") == 0

    def test_negative_infinity_string(self) -> None:
        assert safe_int("-Infinity") == 0

    def test_float_nan(self) -> None:
        """float NaN: int(float('nan')) raises ValueError."""
        assert safe_int(float("nan")) == 0

    def test_float_infinity(self) -> None:
        """float inf: int(float('inf')) raises OverflowError."""
        assert safe_int(float("inf")) == 0

    def test_list_returns_default(self) -> None:
        assert safe_int([1, 2, 3]) == 0

    def test_dict_returns_default(self) -> None:
        assert safe_int({"key": "val"}) == 0


class TestSafeFloat:
    """safe_float converts various types to float safely."""

    def test_int_to_float(self) -> None:
        assert safe_float(42) == 42.0

    def test_float_passthrough(self) -> None:
        assert safe_float(3.14) == pytest.approx(3.14)

    def test_string_numeric(self) -> None:
        assert safe_float("3.14") == pytest.approx(3.14)

    def test_string_scientific(self) -> None:
        assert safe_float("3.40e-13") == pytest.approx(3.40e-13)

    def test_string_non_numeric(self) -> None:
        assert safe_float("hello") == 0.0

    def test_string_empty(self) -> None:
        assert safe_float("") == 0.0

    def test_none_returns_default(self) -> None:
        assert safe_float(None) == 0.0

    def test_custom_default(self) -> None:
        assert safe_float(None, -1.0) == -1.0

    def test_nan_float_returns_default(self) -> None:
        """NaN is not finite -> returns default."""
        assert safe_float(float("nan")) == 0.0

    def test_infinity_returns_default(self) -> None:
        assert safe_float(float("inf")) == 0.0

    def test_negative_infinity_returns_default(self) -> None:
        assert safe_float(float("-inf")) == 0.0

    def test_nan_string_returns_default(self) -> None:
        """'NaN' string parses to float NaN, which is not finite -> default."""
        assert safe_float("NaN") == 0.0

    def test_infinity_string_returns_default(self) -> None:
        """'Infinity' parses to float inf -> not finite -> default."""
        assert safe_float("Infinity") == 0.0

    def test_negative_infinity_string_returns_default(self) -> None:
        assert safe_float("-Infinity") == 0.0

    def test_negative_zero(self) -> None:
        """Negative zero is finite."""
        result = safe_float(-0.0)
        assert result == 0.0

    def test_very_small_float(self) -> None:
        assert safe_float(1e-300) == pytest.approx(1e-300)

    def test_very_large_float(self) -> None:
        assert safe_float(1e300) == pytest.approx(1e300)

    def test_bool_true(self) -> None:
        """bool is a subclass of int -> float(True) = 1.0."""
        assert safe_float(True) == 1.0

    def test_list_returns_default(self) -> None:
        assert safe_float([1.0]) == 0.0

    def test_dict_returns_default(self) -> None:
        assert safe_float({"key": 1.0}) == 0.0

    def test_custom_default_on_nan(self) -> None:
        assert safe_float(float("nan"), 999.0) == 999.0


class TestExtractWdkId:
    """extract_wdk_id extracts an integer ID from a WDK response."""

    def test_standard_payload(self) -> None:
        assert extract_wdk_id({"id": 42}) == 42

    def test_custom_key(self) -> None:
        assert extract_wdk_id({"strategyId": 99}, key="strategyId") == 99

    def test_missing_key(self) -> None:
        assert extract_wdk_id({"other": 42}) is None

    def test_non_int_value(self) -> None:
        """String ID is not extracted (WDK uses Java long)."""
        assert extract_wdk_id({"id": "42"}) is None

    def test_float_value(self) -> None:
        """Float ID is not extracted."""
        assert extract_wdk_id({"id": 42.0}) is None

    def test_none_payload(self) -> None:
        assert extract_wdk_id(None) is None

    def test_non_dict_payload(self) -> None:
        assert extract_wdk_id([42]) is None

    def test_empty_dict(self) -> None:
        assert extract_wdk_id({}) is None

    def test_zero_id(self) -> None:
        """Zero is a valid integer ID."""
        assert extract_wdk_id({"id": 0}) == 0

    def test_negative_id(self) -> None:
        """Negative IDs are technically valid integers."""
        assert extract_wdk_id({"id": -1}) == -1


class TestCoerceStepId:
    """coerce_step_id raises on missing ID."""

    def test_valid_payload(self) -> None:
        assert coerce_step_id({"id": 42}) == 42

    def test_missing_id_raises(self) -> None:
        with pytest.raises(DataParsingError, match="Failed to extract step ID"):
            coerce_step_id({})

    def test_none_payload_raises(self) -> None:
        with pytest.raises(DataParsingError, match="Failed to extract step ID"):
            coerce_step_id(None)

    def test_string_id_raises(self) -> None:
        """String IDs are not accepted."""
        with pytest.raises(DataParsingError, match="Failed to extract step ID"):
            coerce_step_id({"id": "not_an_int"})


class TestExtractGeneList:
    """_extract_gene_list extracts gene IDs from control-test result."""

    def test_basic_extraction(self) -> None:
        result = {"positive": {"intersectionIds": ["G1", "G2"]}}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert len(genes) == 2
        assert genes[0].id == "G1"
        assert genes[1].id == "G2"

    def test_missing_section(self) -> None:
        result: dict[str, object] = {}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert genes == []

    def test_section_not_dict(self) -> None:
        result = {"positive": "invalid"}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert genes == []

    def test_missing_key_in_section(self) -> None:
        result = {"positive": {"otherKey": ["G1"]}}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert genes == []

    def test_none_entries_in_list_filtered(self) -> None:
        """None entries in the list are filtered out."""
        result = {"positive": {"intersectionIds": ["G1", None, "G2"]}}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert len(genes) == 2
        assert genes[0].id == "G1"
        assert genes[1].id == "G2"

    def test_non_list_ids_raw(self) -> None:
        """When ids_raw is not a list."""
        result = {"positive": {"intersectionIds": "not a list"}}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert genes == []

    def test_fallback_from_controls(self) -> None:
        """When section is missing and fallback is enabled, use all_controls minus hit_ids."""
        result: dict[str, object] = {}
        genes = _extract_gene_list(
            result,
            "negative",
            "missingIdsSample",
            fallback_from_controls=True,
            all_controls=["G1", "G2", "G3"],
            hit_ids={"G1"},
        )
        assert len(genes) == 2
        ids = [g.id for g in genes]
        assert "G2" in ids
        assert "G3" in ids
        assert "G1" not in ids

    def test_fallback_not_triggered_when_section_exists(self) -> None:
        """When section exists with a valid list, fallback is NOT used."""
        result = {"negative": {"missingIdsSample": ["G4"]}}
        genes = _extract_gene_list(
            result,
            "negative",
            "missingIdsSample",
            fallback_from_controls=True,
            all_controls=["G1", "G2", "G3"],
            hit_ids={"G1"},
        )
        assert len(genes) == 1
        assert genes[0].id == "G4"

    def test_integer_gene_ids_converted(self) -> None:
        """Non-string entries are converted via str()."""
        result = {"positive": {"intersectionIds": [123, 456]}}
        genes = _extract_gene_list(result, "positive", "intersectionIds")
        assert genes[0].id == "123"
        assert genes[1].id == "456"


class TestExtractIdSet:
    """_extract_id_set extracts a set of IDs."""

    def test_basic_extraction(self) -> None:
        result = {"negative": {"intersectionIds": ["G1", "G2", "G3"]}}
        ids = _extract_id_set(result, "negative", "intersectionIds")
        assert ids == {"G1", "G2", "G3"}

    def test_none_filtered(self) -> None:
        result = {"negative": {"intersectionIds": ["G1", None, "G2"]}}
        ids = _extract_id_set(result, "negative", "intersectionIds")
        assert ids == {"G1", "G2"}

    def test_empty_section(self) -> None:
        result: dict[str, object] = {}
        ids = _extract_id_set(result, "negative", "intersectionIds")
        assert ids == set()

    def test_non_list_value(self) -> None:
        result = {"negative": {"intersectionIds": "not a list"}}
        ids = _extract_id_set(result, "negative", "intersectionIds")
        assert ids == set()

    def test_duplicates_collapsed(self) -> None:
        result = {"negative": {"intersectionIds": ["G1", "G1", "G2"]}}
        ids = _extract_id_set(result, "negative", "intersectionIds")
        assert ids == {"G1", "G2"}


class TestEnrichList:
    """_enrich_list replaces bare GeneInfo with metadata from lookup."""

    def test_basic_enrichment(self) -> None:
        genes = [GeneInfo(id="G1"), GeneInfo(id="G2")]
        lookup = {
            "G1": {"geneName": "Gene1", "organism": "Pf3D7", "product": "kinase"},
        }
        enriched = _enrich_list(genes, lookup)
        assert enriched[0].name == "Gene1"
        assert enriched[0].organism == "Pf3D7"
        assert enriched[0].product == "kinase"
        # G2 not in lookup, returned as-is
        assert enriched[1].id == "G2"
        assert enriched[1].name is None

    def test_empty_lookup(self) -> None:
        genes = [GeneInfo(id="G1")]
        enriched = _enrich_list(genes, {})
        assert enriched[0] is genes[0]

    def test_empty_genes(self) -> None:
        enriched = _enrich_list([], {"G1": {"geneName": "Gene1"}})
        assert enriched == []

    def test_partial_metadata(self) -> None:
        """Lookup entry missing some fields falls back to original GeneInfo.

        Code: str(meta.get("organism", "")) or g.organism
        When key is missing, str("") is falsy, so g.organism (None) is used.
        """
        genes = [GeneInfo(id="G1")]
        lookup = {"G1": {"geneName": "Gene1"}}
        enriched = _enrich_list(genes, lookup)
        assert enriched[0].name == "Gene1"
        assert enriched[0].organism is None  # falls back to g.organism
        assert enriched[0].product is None  # falls back to g.product

    def test_preserves_existing_gene_info_on_empty_lookup_fields(self) -> None:
        """When lookup has empty strings, original GeneInfo fields are preserved.

        Code: str(meta.get("geneName", "")) or g.name
        If geneName is "", str("") is falsy, so g.name is used.
        """
        genes = [GeneInfo(id="G1", name="original_name")]
        lookup = {"G1": {"geneName": "", "organism": "", "product": ""}}
        enriched = _enrich_list(genes, lookup)
        assert enriched[0].name == "original_name"
