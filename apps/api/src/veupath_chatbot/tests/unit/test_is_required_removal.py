"""Tests for isRequired removal — required params use allowEmptyValue / minSelectedCount."""

from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
    find_missing_required_params,
)


class TestFindMissingRequiredParamsWDKCompliant:
    """Verify required-param detection uses only WDK-native fields."""

    def test_allow_empty_false_means_required(self) -> None:
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="string", allow_empty_value=False)}
        missing = find_missing_required_params(specs, {})
        assert missing == ["p1"]

    def test_allow_empty_true_means_not_required(self) -> None:
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="string", allow_empty_value=True)}
        missing = find_missing_required_params(specs, {})
        assert missing == []

    def test_min_selected_count_1_means_required(self) -> None:
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="multi-pick-vocabulary", min_selected_count=1)}
        missing = find_missing_required_params(specs, {})
        assert missing == ["p1"]

    def test_min_selected_count_0_not_required(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1", param_type="multi-pick-vocabulary", allow_empty_value=True, min_selected_count=0,
            )
        }
        missing = find_missing_required_params(specs, {})
        assert missing == []

    def test_no_allow_empty_key_defaults_not_required(self) -> None:
        """When allow_empty_value defaults to False, param IS required."""
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="string")}
        missing = find_missing_required_params(specs, {})
        # allow_empty_value defaults to False -> required
        assert missing == ["p1"]

    def test_allow_empty_true_defaults_not_required(self) -> None:
        """When allow_empty_value is True and no min_selected_count, param is NOT required."""
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="string", allow_empty_value=True)}
        missing = find_missing_required_params(specs, {})
        assert missing == []

    def test_both_allow_empty_false_and_min_selected_1(self) -> None:
        specs = {
            "p1": ParamSpecNormalized(
                name="p1",
                param_type="multi-pick-vocabulary",
                allow_empty_value=False,
                min_selected_count=1,
            )
        }
        missing = find_missing_required_params(specs, {})
        assert missing == ["p1"]

    def test_allow_empty_true_but_min_selected_1_still_required(self) -> None:
        """minSelectedCount >= 1 overrides allow_empty_value=True."""
        specs = {
            "p1": ParamSpecNormalized(
                name="p1",
                param_type="multi-pick-vocabulary",
                allow_empty_value=True,
                min_selected_count=1,
            )
        }
        missing = find_missing_required_params(specs, {})
        assert missing == ["p1"]

    def test_required_param_present_with_value(self) -> None:
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="string", allow_empty_value=False)}
        missing = find_missing_required_params(specs, {"p1": "some_value"})
        assert missing == []

    def test_required_param_present_but_empty(self) -> None:
        specs = {"p1": ParamSpecNormalized(name="p1", param_type="string", allow_empty_value=False)}
        missing = find_missing_required_params(specs, {"p1": ""})
        assert missing == ["p1"]
