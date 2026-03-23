"""Tests for domain/parameters/specs.py."""

from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
    adapt_param_specs_from_search,
    find_input_step_param,
    find_missing_required_params,
    unwrap_search_data,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKNumberParam,
    WDKStringParam,
)


# ---------------------------------------------------------------------------
# find_input_step_param
# ---------------------------------------------------------------------------
class TestFindInputStepParam:
    def test_finds_input_step(self) -> None:
        specs = {
            "organism": ParamSpecNormalized(
                name="organism", param_type="multi-pick-vocabulary"
            ),
            "inputStepId": ParamSpecNormalized(
                name="inputStepId", param_type="input-step"
            ),
        }
        assert find_input_step_param(specs) == "inputStepId"

    def test_no_input_step(self) -> None:
        specs = {
            "organism": ParamSpecNormalized(
                name="organism", param_type="multi-pick-vocabulary"
            ),
        }
        assert find_input_step_param(specs) is None

    def test_empty_specs(self) -> None:
        assert find_input_step_param({}) is None


# ---------------------------------------------------------------------------
# find_missing_required_params
# ---------------------------------------------------------------------------
class TestFindMissingRequiredParams:
    def test_no_required_params(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=True
            )
        }
        missing = find_missing_required_params(specs, {"p1": "val"})
        assert missing == []

    def test_required_param_present(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": "val"})
        assert missing == []

    def test_required_param_missing(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {})
        assert missing == ["p1"]

    def test_required_param_none_value(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": None})
        assert missing == ["p1"]

    def test_required_param_empty_string(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": ""})
        assert missing == ["p1"]

    def test_required_param_empty_list(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": []})
        assert missing == ["p1"]

    def test_required_param_empty_dict(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": {}})
        assert missing == ["p1"]

    def test_not_allow_empty_treated_as_required(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {})
        assert missing == ["p1"]

    def test_allow_empty_not_treated_as_required(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=True
            )
        }
        missing = find_missing_required_params(specs, {})
        assert missing == []

    def test_multi_pick_empty_json_string(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="multi-pick-vocabulary", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": "[]"})
        assert missing == ["p1"]

    def test_multi_pick_empty_list(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="multi-pick-vocabulary", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": []})
        assert missing == ["p1"]

    def test_multi_pick_with_values(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="multi-pick-vocabulary", allow_empty_value=False
            )
        }
        missing = find_missing_required_params(specs, {"p1": '["a"]'})
        assert missing == []

    def test_multiple_missing(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="string", allow_empty_value=False
            ),
            "p2": ParamSpecNormalized(
                name="p2", param_type="string", allow_empty_value=False
            ),
            "p3": ParamSpecNormalized(
                name="p3", param_type="string", allow_empty_value=True
            ),
        }
        missing = find_missing_required_params(specs, {"p3": "val"})
        assert missing == ["p1", "p2"]


# ---------------------------------------------------------------------------
# WDK metadata extraction via ParamSpecNormalized.from_wdk
# ---------------------------------------------------------------------------
class TestWdkMetadataExtraction:
    def test_display_type_extracted(self) -> None:
        param = WDKEnumParam(
            name="org",
            type="multi-pick-vocabulary",
            display_type="treeBox",
        )
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.display_type == "treeBox"

    def test_is_visible_false(self) -> None:
        param = WDKStringParam(
            name="hidden",
            is_visible=False,
            group="_hidden",
        )
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_visible is False
        assert spec.group == "_hidden"

    def test_is_visible_defaults_true(self) -> None:
        param = WDKStringParam(name="vis")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_visible is True

    def test_dependent_params(self) -> None:
        param = WDKStringParam(name="p", dependent_params=["a", "b"])
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.dependent_params == ("a", "b")

    def test_dependent_params_missing(self) -> None:
        param = WDKStringParam(name="p")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.dependent_params == ()

    def test_help_text(self) -> None:
        param = WDKStringParam(name="p", help="some help")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.help == "some help"

    def test_help_missing(self) -> None:
        param = WDKStringParam(name="p")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.help is None

    def test_display_type_defaults_empty(self) -> None:
        param = WDKStringParam(name="p")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.display_type == ""

    def test_group_defaults_empty(self) -> None:
        param = WDKStringParam(name="p")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.group == ""


# ---------------------------------------------------------------------------
# unwrap_search_data
# ---------------------------------------------------------------------------
class TestUnwrapSearchData:
    def test_none_returns_none(self) -> None:
        assert unwrap_search_data(None) is None

    def test_non_dict_returns_none(self) -> None:
        assert unwrap_search_data("not a dict") is None
        assert unwrap_search_data(42) is None

    def test_dict_without_search_data_returns_itself(self) -> None:
        payload = {"parameters": [{"name": "org"}]}
        result = unwrap_search_data(payload)
        assert result is payload

    def test_dict_with_search_data_dict_returns_inner(self) -> None:
        inner = {"parameters": [{"name": "org"}]}
        payload = {"searchData": inner}
        result = unwrap_search_data(payload)
        assert result is inner

    def test_non_dict_search_data_returns_outer(self) -> None:
        """If searchData exists but isn't a dict, return the outer dict."""
        payload = {"searchData": "bad", "parameters": []}
        result = unwrap_search_data(payload)
        assert result is payload

    def test_empty_dict_returns_itself(self) -> None:
        payload: dict[str, object] = {}
        assert unwrap_search_data(payload) is payload


# ---------------------------------------------------------------------------
# ParamSpecNormalized.from_wdk — numeric constraints
# ---------------------------------------------------------------------------
class TestFromWdkNumeric:
    def test_is_number_on_string_param(self) -> None:
        """StringParam can have isNumber=true for numeric constraints."""
        param = WDKStringParam(name="threshold", is_number=True)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_number is True

    def test_increment_from_number_param(self) -> None:
        param = WDKNumberParam(name="n", increment=5)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.increment == 5.0

    def test_max_length_zero_becomes_none(self) -> None:
        """WDK uses length=0 to mean 'no limit'."""
        param = WDKStringParam(name="q", length=0)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.max_length is None

    def test_max_length_negative_becomes_none(self) -> None:
        param = WDKStringParam(name="q", length=-1)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.max_length is None

    def test_max_length_positive_preserved(self) -> None:
        param = WDKStringParam(name="q", length=200)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.max_length == 200

    def test_negative_max_selected_becomes_none(self) -> None:
        param = WDKEnumParam(
            name="organism",
            type="multi-pick-vocabulary",
            max_selected_count=-1,
        )
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.max_selected_count is None


# ---------------------------------------------------------------------------
# adapt_param_specs_from_search
# ---------------------------------------------------------------------------
class TestAdaptParamSpecsFromSearch:
    def test_search_with_no_parameters_returns_empty(self) -> None:
        search = WDKSearch(
            url_segment="GenesByTextSearch",
            full_name="Genes matching text",
            display_name="Text Search",
            description="Detailed description",
            is_analyzable=True,
            parameters=None,
            groups=[],
        )
        result = adapt_param_specs_from_search(search)
        assert result == {}
