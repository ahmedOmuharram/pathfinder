"""Unit tests for WDK parameter discriminated union.

Verifies type discrimination, field parsing, vocabulary handling,
and real-world parameter shapes for all 11 parameter types in
``wdk_parameters.py``.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKModel
from veupath_chatbot.integrations.veupathdb.wdk_parameters import (
    WDKAnswerParam,
    WDKDatasetParam,
    WDKDateParam,
    WDKDateRangeParam,
    WDKEnumParam,
    WDKFilterParam,
    WDKNumberParam,
    WDKNumberRangeParam,
    WDKParameter,
    WDKStringParam,
    WDKTimestampParam,
)
from veupath_chatbot.tests.fixtures.wdk_responses import (
    wdk_dataset_param_json,
    wdk_enum_param_json,
    wdk_filter_param_json,
    wdk_string_param_json,
)

_param_adapter: TypeAdapter[WDKParameter] = TypeAdapter(WDKParameter)


# ---------------------------------------------------------------------------
# Discriminated union routing
# ---------------------------------------------------------------------------


class TestParameterDiscrimination:
    def test_discriminate_string_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "string"})
        assert isinstance(result, WDKStringParam)

    def test_discriminate_number_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "number"})
        assert isinstance(result, WDKNumberParam)

    def test_discriminate_number_range_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "number-range"})
        assert isinstance(result, WDKNumberRangeParam)

    def test_discriminate_date_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "date"})
        assert isinstance(result, WDKDateParam)

    def test_discriminate_date_range_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "date-range"})
        assert isinstance(result, WDKDateRangeParam)

    def test_discriminate_timestamp_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "timestamp"})
        assert isinstance(result, WDKTimestampParam)

    def test_discriminate_single_pick(self) -> None:
        result = _param_adapter.validate_python(
            {"name": "x", "type": "single-pick-vocabulary"}
        )
        assert isinstance(result, WDKEnumParam)

    def test_discriminate_multi_pick(self) -> None:
        result = _param_adapter.validate_python(
            {"name": "x", "type": "multi-pick-vocabulary"}
        )
        assert isinstance(result, WDKEnumParam)

    def test_discriminate_filter_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "filter"})
        assert isinstance(result, WDKFilterParam)

    def test_discriminate_dataset_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "input-dataset"})
        assert isinstance(result, WDKDatasetParam)

    def test_discriminate_answer_param(self) -> None:
        result = _param_adapter.validate_python({"name": "x", "type": "input-step"})
        assert isinstance(result, WDKAnswerParam)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            _param_adapter.validate_python({"name": "x", "type": "unknown"})


# ---------------------------------------------------------------------------
# WDKStringParam
# ---------------------------------------------------------------------------


class TestWDKStringParam:
    def test_basic_string_param(self) -> None:
        data = wdk_string_param_json()
        param = WDKStringParam.model_validate(data)
        assert param.name == "text_expression"
        assert param.type == "string"
        assert param.length == 0

    def test_is_number_flag(self) -> None:
        data = wdk_string_param_json(is_number=True)
        param = WDKStringParam.model_validate(data)
        assert param.is_number is True

    def test_length_zero_means_no_limit(self) -> None:
        data = wdk_string_param_json(length=0)
        param = WDKStringParam.model_validate(data)
        assert param.length == 0

    def test_multiline_flag(self) -> None:
        data = wdk_string_param_json()
        data["isMultiLine"] = True
        param = WDKStringParam.model_validate(data)
        assert param.is_multi_line is True


# ---------------------------------------------------------------------------
# WDKEnumParam
# ---------------------------------------------------------------------------


class TestWDKEnumParam:
    def test_flat_vocabulary_select(self) -> None:
        data = wdk_enum_param_json(display_type="select")
        param = WDKEnumParam.model_validate(data)
        assert param.display_type == "select"
        assert isinstance(param.vocabulary, list)

    def test_flat_vocabulary_checkbox(self) -> None:
        data = wdk_enum_param_json(display_type="checkBox")
        param = WDKEnumParam.model_validate(data)
        assert param.display_type == "checkBox"

    def test_flat_vocabulary_typeahead(self) -> None:
        data = wdk_enum_param_json(display_type="typeAhead")
        param = WDKEnumParam.model_validate(data)
        assert param.display_type == "typeAhead"

    def test_tree_vocabulary_treebox(self) -> None:
        data = wdk_enum_param_json(display_type="treeBox")
        param = WDKEnumParam.model_validate(data)
        assert param.display_type == "treeBox"
        assert isinstance(param.vocabulary, dict)

    def test_single_pick_type(self) -> None:
        data = wdk_enum_param_json(param_type="single-pick-vocabulary")
        param = WDKEnumParam.model_validate(data)
        assert param.type == "single-pick-vocabulary"

    def test_multi_pick_type(self) -> None:
        data = wdk_enum_param_json(param_type="multi-pick-vocabulary")
        param = WDKEnumParam.model_validate(data)
        assert param.type == "multi-pick-vocabulary"

    def test_max_selected_count_unlimited(self) -> None:
        data = wdk_enum_param_json()
        param = WDKEnumParam.model_validate(data)
        assert param.max_selected_count == -1

    def test_count_only_leaves_treebox(self) -> None:
        data = wdk_enum_param_json(display_type="treeBox")
        param = WDKEnumParam.model_validate(data)
        assert param.count_only_leaves is True


# ---------------------------------------------------------------------------
# WDKFilterParam
# ---------------------------------------------------------------------------


class TestWDKFilterParam:
    def test_filter_with_ontology(self) -> None:
        data = wdk_filter_param_json()
        param = WDKFilterParam.model_validate(data)
        assert isinstance(param.ontology, list)
        assert len(param.ontology) > 0

    def test_filter_with_values(self) -> None:
        data = wdk_filter_param_json()
        data["values"] = {"key": "val"}
        param = WDKFilterParam.model_validate(data)
        assert isinstance(param.values, dict)


# ---------------------------------------------------------------------------
# WDKDatasetParam
# ---------------------------------------------------------------------------


class TestWDKDatasetParam:
    def test_dataset_with_parsers(self) -> None:
        data = wdk_dataset_param_json()
        param = WDKDatasetParam.model_validate(data)
        assert isinstance(param.parsers, list)
        assert len(param.parsers) > 0

    def test_default_id_list(self) -> None:
        data = wdk_dataset_param_json()
        param = WDKDatasetParam.model_validate(data)
        assert param.default_id_list is None or isinstance(param.default_id_list, str)


# ---------------------------------------------------------------------------
# Base parameter fields
# ---------------------------------------------------------------------------


class TestBaseParameterFields:
    def test_inherits_from_wdk_model(self) -> None:
        data = wdk_string_param_json()
        param = WDKStringParam.model_validate(data)
        assert isinstance(param, WDKModel)

    def test_dependent_params_present(self) -> None:
        data = wdk_string_param_json()
        param = WDKStringParam.model_validate(data)
        assert isinstance(param.dependent_params, list)

    def test_dependent_params_non_empty(self) -> None:
        data = wdk_string_param_json()
        data["dependentParams"] = ["organism", "taxon"]
        param = WDKStringParam.model_validate(data)
        assert param.dependent_params == ["organism", "taxon"]

    def test_initial_display_value(self) -> None:
        data = wdk_enum_param_json()
        param = WDKEnumParam.model_validate(data)
        assert isinstance(param.initial_display_value, str)

    def test_properties_dict(self) -> None:
        data = wdk_string_param_json()
        data["properties"] = {"organisms": ["val"]}
        param = WDKStringParam.model_validate(data)
        assert isinstance(param.properties, dict)
        assert param.properties == {"organisms": ["val"]}

    def test_allow_empty_value(self) -> None:
        data = wdk_string_param_json()
        data["allowEmptyValue"] = True
        param = WDKStringParam.model_validate(data)
        assert param.allow_empty_value is True


# ---------------------------------------------------------------------------
# Real-world parameter parsing through the union
# ---------------------------------------------------------------------------


class TestRealWorldParams:
    def test_parse_plasmodb_organism_param(self) -> None:
        data = wdk_enum_param_json(name="organism", display_type="treeBox")
        result = _param_adapter.validate_python(data)
        assert isinstance(result, WDKEnumParam)
        assert result.name == "organism"

    def test_parse_plasmodb_text_expression(self) -> None:
        data = wdk_string_param_json(name="text_expression")
        result = _param_adapter.validate_python(data)
        assert isinstance(result, WDKStringParam)

    def test_parse_plasmodb_dataset_param(self) -> None:
        data = wdk_dataset_param_json()
        result = _param_adapter.validate_python(data)
        assert isinstance(result, WDKDatasetParam)

    def test_parse_all_param_types_in_search(self) -> None:
        params_data = [
            wdk_string_param_json(name="text_expression"),
            wdk_enum_param_json(name="organism", display_type="treeBox"),
            wdk_filter_param_json(name="gene_boolean_filter_array"),
        ]
        expected_types = [WDKStringParam, WDKEnumParam, WDKFilterParam]
        for data, expected_type in zip(params_data, expected_types, strict=True):
            result = _param_adapter.validate_python(data)
            assert isinstance(result, expected_type)


# ---------------------------------------------------------------------------
# ParamSpecNormalized.from_wdk() bridge
# ---------------------------------------------------------------------------


class TestParamSpecBridge:
    """Tests for ParamSpecNormalized.from_wdk() bridge."""

    def test_from_wdk_string_param(self) -> None:
        param = WDKStringParam.model_validate(wdk_string_param_json())
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.name == "text_expression"
        assert spec.param_type == "string"
        assert spec.is_number is False

    def test_from_wdk_enum_param(self) -> None:
        param = WDKEnumParam.model_validate(wdk_enum_param_json())
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.name == "organism"
        assert spec.param_type == "multi-pick-vocabulary"
        assert spec.vocabulary is not None

    def test_from_wdk_preserves_vocabulary(self) -> None:
        param = WDKEnumParam.model_validate(wdk_enum_param_json(display_type="treeBox"))
        spec = ParamSpecNormalized.from_wdk(param)
        assert isinstance(spec.vocabulary, dict)  # tree vocab

    def test_from_wdk_preserves_constraints(self) -> None:
        param = WDKEnumParam.model_validate(wdk_enum_param_json())
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.min_selected_count == 1
        assert spec.max_selected_count is None  # -1 -> None

    def test_from_wdk_preserves_dependent(self) -> None:
        data = wdk_string_param_json()
        data["dependentParams"] = ["organism", "taxon"]
        param = WDKStringParam.model_validate(data)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.dependent_params == ("organism", "taxon")

    def test_from_wdk_initial_display_value(self) -> None:
        param = WDKEnumParam.model_validate(wdk_enum_param_json())
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.initial_display_value is not None

    def test_from_wdk_number_flag(self) -> None:
        param = WDKStringParam.model_validate(wdk_string_param_json(is_number=True))
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_number is True

    def test_from_wdk_count_only_leaves(self) -> None:
        param = WDKEnumParam.model_validate(wdk_enum_param_json(display_type="treeBox"))
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.count_only_leaves is True
