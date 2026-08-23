"""What a parameter document publishes about visibility and dependency.

``getRequiredParams()`` returns the whole parameter map and the validation loop
iterates it unfiltered, so ``isVisible`` decides nothing but drawing.
"""

from __future__ import annotations

from pathlib import Path

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.parameters.specs import (
    ParamSpecNormalized,
    fill_hidden_required_defaults,
    filled_hidden_defaults,
    topological_fill_order,
)
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKReporter,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.services.catalog.param_adapters import adapt_param_specs_from_search

_SOURCE_ROOT = Path(__file__).resolve().parents[4]


def _search(name: str) -> WDKSearch:
    return WDKSearchResponse.model_validate(load_recorded(name).json_body()).search_data


def _specs_with_dependents(
    dependents: tuple[str, ...],
) -> dict[str, ParamSpecNormalized]:
    return {
        "a": ParamSpecNormalized(
            name="a", param_type="string", dependent_params=dependents
        ),
        "b": ParamSpecNormalized(name="b", param_type="string"),
        "c": ParamSpecNormalized(name="c", param_type="string"),
    }


class TestWdkParam011HiddenIsPresentationOnly:
    def test_wdk_param_011_a_hidden_parameter_is_published(self) -> None:
        search = _search("search_with_a_hidden_required_parameter")

        hidden = [p for p in search.parameters or [] if not p.is_visible]

        assert [p.name for p in hidden] == ["eda_dataset_id"]

    def test_wdk_param_011_a_hidden_parameter_is_in_param_names(self) -> None:
        search = _search("search_with_a_hidden_required_parameter")

        assert "eda_dataset_id" in search.param_names

    def test_wdk_param_011_a_hidden_parameter_stays_required(self) -> None:
        search = _search("search_with_a_hidden_required_parameter")
        specs = adapt_param_specs_from_search(search)

        assert specs["eda_dataset_id"].allow_empty_value is False
        assert specs["eda_dataset_id"].initial_display_value

    def test_wdk_param_011_a_hidden_parameter_survives_normalization(self) -> None:
        search = _search("search_with_a_hidden_required_parameter")

        specs = adapt_param_specs_from_search(search)

        assert sorted(specs) == sorted(search.param_names)

    def test_wdk_param_011_a_client_must_supply_it_so_pathfinder_fills_it(self) -> None:
        specs = adapt_param_specs_from_search(
            _search("search_with_a_hidden_required_parameter")
        )

        filled = fill_hidden_required_defaults(specs, {})

        assert "eda_dataset_id" in filled
        assert filled_hidden_defaults(specs, {}) == ["eda_dataset_id"]


class TestWdkVocab003DependentParamsPointsAtChildren:
    def test_wdk_vocab_003_the_field_lists_the_parameters_that_depend_on_it(
        self,
    ) -> None:
        specs = adapt_param_specs_from_search(_search("search_genes_by_location"))

        assert specs["organismSinglePick"].dependent_params == ("chromosomeOptional",)

    def test_wdk_vocab_003_the_parameter_that_depends_reports_nothing(self) -> None:
        # To find a parameter's parents you invert the map; no field gives them.
        specs = adapt_param_specs_from_search(_search("search_genes_by_location"))

        assert specs["chromosomeOptional"].dependent_params == ()

    def test_wdk_vocab_003_the_parents_come_from_inverting_the_map(self) -> None:
        specs = adapt_param_specs_from_search(_search("search_genes_by_location"))

        parents = {
            child: {n for n, s in specs.items() if child in s.dependent_params}
            for child in specs
        }

        assert parents["chromosomeOptional"] == {"organismSinglePick"}
        assert parents["organismSinglePick"] == set()

    def test_wdk_vocab_003_the_order_of_the_list_changes_nothing(self) -> None:
        # The backing collection is a HashSet, so the same dependency set
        # arrives in a different order on the next search. Compare as sets.
        forwards = topological_fill_order(_specs_with_dependents(("b", "c")))
        backwards = topological_fill_order(_specs_with_dependents(("c", "b")))

        assert set(forwards) == set(backwards)
        for order in (forwards, backwards):
            assert order.index("a") < min(order.index("b"), order.index("c"))


class TestWdkAns006ScopesAreAdviceToTheClient:
    def test_wdk_ans_006_an_empty_scope_list_is_not_a_closed_door(self) -> None:
        reporter = WDKReporter(name="json", scopes=[])

        assert reporter.name == "json"
        assert reporter.scopes == []

    def test_wdk_ans_006_nothing_but_the_model_reads_scopes(self) -> None:
        # A client picking a reporter to CALL must not filter on scopes.
        readers = [
            path.relative_to(_SOURCE_ROOT).as_posix()
            for path in _SOURCE_ROOT.rglob("*.py")
            if "tests/" not in path.relative_to(_SOURCE_ROOT).as_posix()
            and ".scopes" in path.read_text()
        ]

        assert readers == []
