"""Unit tests for dependent parameter refresh endpoint."""

from veupath_chatbot.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKStringParam,
)
from veupath_chatbot.transport.http.routers.sites.params import (
    _build_param_specs_from_list,
)


class TestBuildParamSpecsFromList:
    """Test converting WDKParameter list to ParamSpecResponse list."""

    def test_enum_param_includes_vocabulary(self) -> None:
        param = WDKEnumParam(
            name="organism",
            display_name="Organism",
            type="single-pick-vocabulary",
            allow_empty_value=False,
            is_visible=True,
            dependent_params=["gene_list"],
            vocabulary=[["pfal", "P. falciparum"], ["pviv", "P. vivax"]],
            display_type="select",
            min_selected_count=1,
            max_selected_count=1,
            count_only_leaves=False,
            help="Choose an organism",
        )
        result = _build_param_specs_from_list([param])
        assert len(result) == 1
        spec = result[0]
        assert spec.name == "organism"
        assert spec.vocabulary is not None
        assert spec.dependent_params == ["gene_list"]

    def test_string_param_is_number(self) -> None:
        param = WDKStringParam(
            name="threshold",
            display_name="Threshold",
            type="string",
            allow_empty_value=True,
            is_visible=True,
            dependent_params=[],
            is_number=True,
        )
        result = _build_param_specs_from_list([param])
        assert len(result) == 1
        assert result[0].is_number is True

    def test_empty_list_returns_empty(self) -> None:
        result = _build_param_specs_from_list([])
        assert result == []

    def test_results_sorted_by_name(self) -> None:
        params = [
            WDKStringParam(
                name="z_param",
                display_name="Z",
                type="string",
                allow_empty_value=True,
                is_visible=True,
                dependent_params=[],
                is_number=False,
            ),
            WDKStringParam(
                name="a_param",
                display_name="A",
                type="string",
                allow_empty_value=True,
                is_visible=True,
                dependent_params=[],
                is_number=False,
            ),
        ]
        result = _build_param_specs_from_list(params)
        assert result[0].name == "a_param"
        assert result[1].name == "z_param"
