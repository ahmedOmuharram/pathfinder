"""What a search document says, and which parts of it are advice.

``supplementWithBasicParamInfo`` writes ``groups`` and ``paramNames`` from one
call, so they agree on membership by construction. ``paramNames`` is the flat
one.
"""

from __future__ import annotations

from pathlib import Path

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.integrations.veupathdb.discovery import SearchCatalog
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search

_SOURCE_ROOT = Path(__file__).resolve().parents[4]


def _genes_by_location() -> WDKSearch:
    return WDKSearchResponse.model_validate(
        load_recorded("search_genes_by_location").json_body()
    ).search_data


class TestWdkSearch004ParamNamesIsTheParameterList:
    def test_wdk_search_004_the_common_case_is_one_synthetic_group(self) -> None:
        search = _genes_by_location()

        assert [g.name for g in search.groups] == ["empty"]
        assert search.groups[0].display_type == "empty"

    def test_wdk_search_004_the_group_holds_every_parameter(self) -> None:
        search = _genes_by_location()

        assert search.groups[0].parameters == search.param_names

    def test_wdk_search_004_the_specs_come_from_the_parameter_list(self) -> None:
        search = _genes_by_location()

        specs = adapt_param_specs_from_search(search)

        assert sorted(specs) == sorted(search.param_names)

    def test_wdk_search_004_a_group_describes_no_parameter_of_its_own(self) -> None:
        # Its state is a name and four presentation fields.
        group = _genes_by_location().groups[0]

        assert set(group.model_dump(by_alias=True)) == {
            "name",
            "displayName",
            "description",
            "isVisible",
            "displayType",
            "parameters",
        }


class TestWdkSearch003AvailabilityIsADeploymentFact:
    def test_wdk_search_003_a_catalog_belongs_to_one_site(self) -> None:
        plasmo, toxo = SearchCatalog("plasmodb"), SearchCatalog("toxodb")

        assert plasmo.site_id == "plasmodb"
        assert toxo.site_id == "toxodb"

    def test_wdk_search_003_two_sites_do_not_share_a_search_set(self) -> None:
        plasmo, toxo = SearchCatalog("plasmodb"), SearchCatalog("toxodb")
        only_here = WDKSearch(urlSegment="GenesBySpanLogic")
        plasmo._searches["transcript"] = [only_here]

        assert plasmo.find_record_type_for_search("GenesBySpanLogic") == "transcript"
        assert toxo.find_record_type_for_search("GenesBySpanLogic") is None

    def test_wdk_search_003_no_search_list_is_written_into_the_code(self) -> None:
        # A list hardcoded from one site is wrong for the next by a third.
        catalog_source = (_SOURCE_ROOT / "integrations" / "veupathdb").rglob("*.py")
        offenders = [
            path.name
            for path in catalog_source
            if "GenesByMolecularWeight" in path.read_text()
        ]

        assert offenders == []
