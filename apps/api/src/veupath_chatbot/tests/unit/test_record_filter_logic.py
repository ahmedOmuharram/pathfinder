"""Tests for the server-side record filtering logic used in experiment and gene set results.

The filterAttribute/filterValue pattern is a PathFinder extension (not a WDK
native mechanism).  WDK's own filtering happens through ``answerSpec.viewFilters``
and ``answerSpec.columnFilters`` on the step resource.  Our server-side filter
fetches all records from WDK and filters in Python, returning a paginated
subset that matches ``attrs[filterAttribute] == filterValue``.

These tests verify the filtering and pagination logic directly, without
requiring a running API server.
"""

from typing import cast

from veupath_chatbot.platform.types import JSONObject, JSONValue


def _filter_records(
    records: list[JSONObject],
    filter_attribute: str,
    filter_value: str,
    offset: int,
    limit: int,
) -> dict[str, object]:
    """Reproduce the filtering logic from the route handlers.

    This mirrors the inline code in both:
    - ``experiments/results.py::get_experiment_records``
    - ``gene_sets.py::get_gene_set_records``
    """
    filtered: list[JSONValue] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        attrs = r.get("attributes")
        if isinstance(attrs, dict) and attrs.get(filter_attribute) == filter_value:
            filtered.append(r)
    page = filtered[offset : offset + limit]
    return {
        "records": cast(JSONValue, page),
        "meta": {
            "totalCount": len(filtered),
            "displayTotalCount": len(filtered),
            "responseCount": len(page),
            "pagination": {"offset": offset, "numRecords": limit},
        },
    }


def _make_record(gene_id: str, organism: str) -> JSONObject:
    """Build a minimal WDK-style record."""
    return {
        "id": [{"name": "gene_source_id", "value": gene_id}],
        "attributes": {
            "gene_id": gene_id,
            "organism": organism,
        },
    }


class TestRecordFilterLogic:
    """Tests for the inline filterAttribute/filterValue logic."""

    def test_filters_by_exact_attribute_match(self) -> None:
        records = [
            _make_record("G1", "Plasmodium falciparum 3D7"),
            _make_record("G2", "Plasmodium vivax Sal-1"),
            _make_record("G3", "Plasmodium falciparum 3D7"),
        ]
        result = _filter_records(
            records, "organism", "Plasmodium falciparum 3D7", offset=0, limit=50
        )
        assert result["meta"]["totalCount"] == 2
        assert len(result["records"]) == 2

    def test_returns_empty_when_no_match(self) -> None:
        records = [
            _make_record("G1", "Plasmodium falciparum 3D7"),
        ]
        result = _filter_records(
            records, "organism", "Toxoplasma gondii ME49", offset=0, limit=50
        )
        assert result["meta"]["totalCount"] == 0
        assert result["records"] == []

    def test_pagination_offset_and_limit(self) -> None:
        records = [_make_record(f"G{i}", "Pf3D7") for i in range(10)]
        result = _filter_records(records, "organism", "Pf3D7", offset=3, limit=4)
        assert result["meta"]["totalCount"] == 10
        assert result["meta"]["responseCount"] == 4
        page = result["records"]
        assert len(page) == 4
        # First record in page should be G3 (0-indexed offset=3)
        assert page[0]["attributes"]["gene_id"] == "G3"
        assert page[3]["attributes"]["gene_id"] == "G6"

    def test_pagination_at_end_returns_partial_page(self) -> None:
        records = [_make_record(f"G{i}", "Pf3D7") for i in range(5)]
        result = _filter_records(records, "organism", "Pf3D7", offset=3, limit=50)
        assert result["meta"]["totalCount"] == 5
        assert len(result["records"]) == 2  # Only G3, G4 remain

    def test_skips_non_dict_records(self) -> None:
        records: list[JSONObject] = [
            _make_record("G1", "Pf3D7"),
            "not a dict",  # type: ignore[list-item]
            _make_record("G2", "Pf3D7"),
        ]
        result = _filter_records(records, "organism", "Pf3D7", offset=0, limit=50)
        assert result["meta"]["totalCount"] == 2

    def test_skips_records_without_attributes_dict(self) -> None:
        records: list[JSONObject] = [
            {"id": [{"name": "pk", "value": "G1"}], "attributes": "not a dict"},
            _make_record("G2", "Pf3D7"),
        ]
        result = _filter_records(records, "organism", "Pf3D7", offset=0, limit=50)
        assert result["meta"]["totalCount"] == 1

    def test_missing_attribute_does_not_match(self) -> None:
        records = [
            {
                "id": [{"name": "pk", "value": "G1"}],
                "attributes": {"gene_id": "G1"},
            }
        ]
        result = _filter_records(records, "organism", "Pf3D7", offset=0, limit=50)
        assert result["meta"]["totalCount"] == 0

    def test_empty_records_list(self) -> None:
        result = _filter_records([], "organism", "Pf3D7", offset=0, limit=50)
        assert result["meta"]["totalCount"] == 0
        assert result["records"] == []

    def test_filter_value_empty_string_matches_empty_attribute(self) -> None:
        records: list[JSONObject] = [
            {
                "id": [{"name": "pk", "value": "G1"}],
                "attributes": {"organism": ""},
            },
            _make_record("G2", "Pf3D7"),
        ]
        result = _filter_records(records, "organism", "", offset=0, limit=50)
        assert result["meta"]["totalCount"] == 1
        assert result["records"][0]["attributes"]["organism"] == ""
