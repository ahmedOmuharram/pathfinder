"""How a search is addressed, and under which record type.

A search carries two names and only the url segment is a path segment. The
record type in the path is not decoration: supply the wrong one and the search
is simply not there.
"""

from __future__ import annotations

from typing import Any

import pytest

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.discovery import SearchCatalog
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse


class _PathRecorder:
    """Captures the request path instead of reaching WDK."""

    def __init__(self, body: Any) -> None:
        self.body = body
        self.paths: list[str] = []

    async def __call__(self, path: str, **_: object) -> Any:
        self.paths.append(path)
        return self.body


def _molecular_weight() -> WDKSearchResponse:
    return WDKSearchResponse.model_validate(
        load_recorded("search_genes_by_molecular_weight").json_body()
    )


class TestWdkSearch002TheUrlSegmentIsTheAddress:
    def test_wdk_search_002_a_search_carries_two_different_names(self) -> None:
        search = _molecular_weight().search_data

        assert search.url_segment == "GenesByMolecularWeight"
        assert search.full_name == "GeneQuestions.GenesByMolecularWeight"

    async def test_wdk_search_002_the_request_path_carries_the_url_segment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        get = _PathRecorder(
            load_recorded("search_genes_by_molecular_weight").json_body()
        )
        monkeypatch.setattr(client, "get", get)

        await client.get_search_details("transcript", "GenesByMolecularWeight")

        assert get.paths == ["/record-types/transcript/searches/GenesByMolecularWeight"]

    async def test_wdk_search_002_the_full_name_never_reaches_the_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        search = _molecular_weight().search_data
        get = _PathRecorder(
            load_recorded("search_genes_by_molecular_weight").json_body()
        )
        monkeypatch.setattr(client, "get", get)

        await client.get_search_details("transcript", search.url_segment)

        assert search.full_name not in get.paths[0]

    def test_wdk_search_002_the_full_name_is_a_404(self) -> None:
        recorded = load_recorded("search_by_full_name")

        assert recorded.provenance.status == 404
        assert recorded.text_body().startswith(
            "Resource 'search: GeneQuestions.GenesByMolecularWeight' does not exist."
        )

    def test_wdk_search_002_the_full_name_is_kept_as_data(self) -> None:
        # It is the name a step's searchName carries and error messages use.
        assert _molecular_weight().search_data.full_name != ""


class TestWdkSearch001ASearchBelongsToOneRecordClass:
    def test_wdk_search_001_the_wrong_record_type_is_a_404(self) -> None:
        recorded = load_recorded("search_under_the_wrong_record_type")

        assert recorded.provenance.status == 404
        assert recorded.text_body().strip() == (
            'There is no search "GenesByMolecularWeight" associated with '
            'record type "OrganismRecordClass"'
        )

    def test_wdk_search_001_the_refusal_names_the_record_class_full_name(self) -> None:
        # The path segment is the url segment; the comparison is against the
        # record class full name.
        body = load_recorded("search_under_the_wrong_record_type").text_body()

        assert "OrganismRecordClass" in body
        assert 'record type "organism"' not in body

    def test_wdk_search_001_a_search_declares_one_output_record_class(self) -> None:
        search = _molecular_weight().search_data

        assert search.output_record_class_name == "transcript"

    def test_wdk_search_001_the_catalog_binds_a_search_to_one_record_type(self) -> None:
        # A client that caches "search X exists" without the record type it
        # exists under has cached half a fact.
        catalog = SearchCatalog("plasmodb")
        catalog._searches["transcript"] = [WDKSearch(urlSegment="GenesByExonCount")]
        catalog._searches["organism"] = [WDKSearch(urlSegment="OrganismsByTaxon")]

        assert catalog.find_record_type_for_search("GenesByExonCount") == "transcript"
        assert catalog.find_search("organism", "GenesByExonCount") is None
        assert catalog.find_search("transcript", "GenesByExonCount") is not None
