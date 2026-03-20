"""Edge-case and bug-hunting tests for domain/parameters."""

import json
import math

import pytest

from veupath_chatbot.domain.parameters._decode_values import (
    decode_values,
    parse_json5_value,
)
from veupath_chatbot.domain.parameters._value_helpers import (
    handle_empty,
    stringify,
    validate_multi_count,
)
from veupath_chatbot.domain.parameters.canonicalize import (
    ParameterCanonicalizer,
)
from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
    adapt_param_specs,
    extract_param_specs,
    find_missing_required_params,
)
from veupath_chatbot.domain.parameters.vocab_utils import (
    flatten_vocab,
    match_vocab_value,
    normalize_vocab_key,
    numeric_equivalent,
)
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.fixtures.builders import ParamSpecConfig, make_param_spec


def _canonicalizer(*specs: ParamSpecNormalized) -> ParameterCanonicalizer:
    return ParameterCanonicalizer(specs={s.name: s for s in specs})


def _normalizer(*specs: ParamSpecNormalized) -> ParameterNormalizer:
    return ParameterNormalizer(specs={s.name: s for s in specs})


# ===========================================================================
# 1. decode_values edge cases
# ===========================================================================


class TestDecodeValuesEdgeCases:
    """Edge cases for decode_values."""

    def test_unicode_string_passthrough(self) -> None:
        """Unicode values should pass through cleanly."""
        result = decode_values("\u00e9t\u00e9", "p")  # "ete" with accents
        assert result == ["\u00e9t\u00e9"]

    def test_unicode_in_json_array(self) -> None:
        result = decode_values('["\u00e9t\u00e9", "\u00fc"]', "p")
        assert result == ["\u00e9t\u00e9", "\u00fc"]

    def test_unicode_csv(self) -> None:
        result = decode_values("\u00e9t\u00e9,\u00fc", "p")
        assert result == ["\u00e9t\u00e9", "\u00fc"]

    def test_sql_injection_not_executed(self) -> None:
        """SQL injection strings should be treated as plain values."""
        injection = "'; DROP TABLE genes; --"
        result = decode_values(injection, "p")
        # Contains comma, so CSV parsing applies
        # The important thing is we get string values, not executed SQL
        assert all(isinstance(v, str) for v in result)

    def test_deeply_nested_json_string(self) -> None:
        """JSON string containing a dict parses via json5 and is returned as [dict].

        The raw value is a *string*, so it enters the string branch.
        parse_json5_value returns a dict which is not None, so [dict] is returned.
        """
        nested = json.dumps({"a": {"b": {"c": [1, 2, 3]}}})
        result = decode_values(nested, "p")
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["a"]["b"]["c"] == [1, 2, 3]

    def test_json5_null_becomes_null_string(self) -> None:
        """'null' parses as None via json5, then gets filtered, falls to plain string."""
        result = decode_values("null", "p")
        assert result == ["null"]

    def test_boolean_false_not_filtered(self) -> None:
        """False is falsy but should NOT be filtered from lists."""
        result = decode_values([False, 0, "", None], "p")
        # None is filtered, but False, 0, "" should remain
        assert result == [False, 0, ""]

    def test_zero_integer_not_filtered(self) -> None:
        """0 is falsy but should be kept."""
        result = decode_values(0, "p")
        assert result == [0]

    def test_float_zero_not_filtered(self) -> None:
        result = decode_values(0.0, "p")
        assert result == [0.0]

    def test_empty_json_array_string(self) -> None:
        """'[]' should parse to empty list."""
        result = decode_values("[]", "p")
        assert result == []

    def test_json_array_of_nulls(self) -> None:
        """'[null, null]' should parse and filter out all nulls."""
        result = decode_values("[null, null]", "p")
        assert result == []

    def test_csv_with_only_commas(self) -> None:
        """String of just commas should produce empty list."""
        result = decode_values(",,,", "p")
        assert result == []

    def test_csv_with_quoted_fields(self) -> None:
        """CSV with properly quoted fields containing commas."""
        result = decode_values('"one, two",three', "p")
        assert result == ["one, two", "three"]

    def test_very_long_string(self) -> None:
        """Very long strings should not cause issues."""
        long_val = "x" * 100_000
        result = decode_values(long_val, "p")
        assert result == [long_val]

    def test_newline_in_string(self) -> None:
        """Newlines in strings are not treated as delimiters by decode_values."""
        result = decode_values("line1\nline2", "p")
        # No comma, so it's a plain string
        assert result == ["line1\nline2"]

    def test_tab_separated_string(self) -> None:
        """Tab-separated strings are treated as a single value."""
        result = decode_values("val1\tval2", "p")
        assert result == ["val1\tval2"]

    def test_set_with_multiple_items(self) -> None:
        """Sets should be converted to lists (order may vary)."""
        result = decode_values({"a", "b"}, "p")
        assert sorted(result) == ["a", "b"]

    def test_nested_list_preserved(self) -> None:
        """Nested lists in a list value are preserved."""
        result = decode_values([[1, 2], [3, 4]], "p")
        assert result == [[1, 2], [3, 4]]


class TestParseJson5ValueEdgeCases:
    def test_infinity_string(self) -> None:
        """'Infinity' may be parsed by json5 as a number."""
        result = parse_json5_value("Infinity")
        # json5 supports Infinity
        assert result == float("inf") or result is None

    def test_nan_string(self) -> None:
        """'NaN' may be parsed by json5."""
        result = parse_json5_value("NaN")
        # json5 supports NaN
        if result is not None:
            assert math.isnan(result)

    def test_single_quoted_string(self) -> None:
        """json5 supports single-quoted strings."""
        result = parse_json5_value("'hello'")
        assert result == "hello"

    def test_trailing_comma_in_array(self) -> None:
        """json5 supports trailing commas."""
        result = parse_json5_value("[1, 2, 3,]")
        assert result == [1, 2, 3]

    def test_comments_in_json5(self) -> None:
        """json5 supports comments."""
        result = parse_json5_value('{"a": 1 /* comment */}')
        assert result == {"a": 1}


# ===========================================================================
# 2. vocab_utils edge cases
# ===========================================================================


class TestNumericEquivalentEdgeCases:
    def test_very_large_numbers(self) -> None:
        large = str(10**15)
        assert numeric_equivalent(large, large) is True

    def test_very_small_numbers(self) -> None:
        assert numeric_equivalent("0.000000001", "0.000000001") is True

    def test_negative_zero_vs_positive_zero(self) -> None:
        assert numeric_equivalent("-0.0", "0.0") is True

    def test_different_precision_floats(self) -> None:
        """WDK often sends '3.14' but strategies may have '3.140000'."""
        assert numeric_equivalent("3.14", "3.140000") is True

    def test_leading_zeros(self) -> None:
        assert numeric_equivalent("007", "7") is True

    def test_plus_sign(self) -> None:
        assert numeric_equivalent("+42", "42") is True

    def test_unicode_digits(self) -> None:
        """Python float() can parse Arabic-Indic digits (U+0661 = Arabic 1)."""
        # This is a known Python behavior: float() handles Unicode digits
        assert numeric_equivalent("\u0661", "1") is True  # Arabic digit 1

    def test_non_numeric_unicode(self) -> None:
        """Non-digit unicode should fail gracefully."""
        assert numeric_equivalent("\u4e00", "1") is False  # CJK character


class TestNormalizeVocabKeyEdgeCases:
    def test_unicode_text(self) -> None:
        """Unicode characters should be preserved."""
        result = normalize_vocab_key("  H\u00e9llo W\u00f6rld  ")
        assert result == "h\u00e9llo w\u00f6rld"

    def test_mixed_whitespace(self) -> None:
        """Tabs, newlines, and multiple spaces should all collapse."""
        result = normalize_vocab_key("a\t\n  b")
        assert result == "a b"


class TestFlattenVocabEdgeCases:
    def test_tree_with_missing_data_field(self) -> None:
        """A tree node without 'data' should still walk children."""
        vocab = {
            "children": [
                {"data": {"term": "child1", "display": "Child 1"}, "children": []},
            ],
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        # Root has no data field: data defaults to {} via .get("data", {})
        assert len(entries) == 2
        # First entry (root) has display=None, value=None
        assert entries[0] == {"display": None, "value": None}
        assert entries[1]["value"] == "child1"

    def test_tree_with_empty_data_dict(self) -> None:
        vocab = {
            "data": {},
            "children": [],
        }
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 1
        assert entries[0] == {"display": None, "value": None}

    def test_list_with_empty_inner_list(self) -> None:
        """Empty inner lists are skipped -- only valid pairs are returned."""
        vocab = [[], ["val1", "Display 1"]]
        entries = flatten_vocab(vocab)
        assert len(entries) == 1
        assert entries[0]["value"] == "val1"

    def test_mixed_list_types(self) -> None:
        """Lists can contain pairs, dicts, and plain values."""
        vocab = [
            ["pair_val", "Pair Display"],
            {"term": "dict_term", "display": "Dict Display"},
            "plain_string",
        ]
        entries = flatten_vocab(vocab, prefer_term=True)
        assert len(entries) == 3
        assert entries[0]["value"] == "pair_val"
        assert entries[1]["value"] == "dict_term"
        assert entries[2]["value"] == "plain_string"


class TestMatchVocabValueEdgeCases:
    def test_empty_string_value_with_vocab(self) -> None:
        """Empty string value should not match any vocab entry."""
        vocab = [["a", "A"]]
        with pytest.raises(ValidationError):
            match_vocab_value(vocab=vocab, param_name="p", value="")

    def test_match_by_numeric_display(self) -> None:
        """Numeric matching on display field."""
        vocab = [["internal_42", "42.0"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="42")
        assert result == "internal_42"

    def test_match_by_numeric_value_field(self) -> None:
        """Numeric matching on value field when display doesn't match."""
        vocab = [["42.0", "Some Label"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="42")
        assert result == "42.0"

    # BUG: match_vocab_value returns `raw_value or display or value` for display match.
    # If raw_value is empty string "", it's falsy, so it falls through to `display`.
    # This means a vocab entry with value="" and display="X" would return "X" instead of "".
    def test_empty_raw_value_display_match_returns_display(self) -> None:
        """When raw_value is empty string and display matches, display is returned.

        This could be a bug if the canonical value is intentionally empty string.
        The current behavior returns the display string instead.
        """
        vocab = {
            "data": {"term": "", "display": "All"},
            "children": [],
        }
        result = match_vocab_value(vocab=vocab, param_name="p", value="All")
        # BUG: raw_value is "" (falsy), so `raw_value or display or value` returns "All"
        # If the intent was to use the term "" as the canonical value, this is wrong.
        assert result == "All"

    def test_none_display_and_none_value_in_entry(self) -> None:
        """Entry with all None fields should not match anything."""
        vocab = [{"term": None, "display": None}]
        with pytest.raises(ValidationError):
            match_vocab_value(vocab=vocab, param_name="p", value="anything")

    def test_whitespace_only_value_stripped(self) -> None:
        """Whitespace-only value should be stripped and matched."""
        vocab = [["val", "Display"]]
        result = match_vocab_value(vocab=vocab, param_name="p", value="  Display  ")
        assert result == "val"

    def test_case_sensitive_matching(self) -> None:
        """Vocab matching is case-sensitive (exact match)."""
        vocab = [["val", "Display"]]
        with pytest.raises(ValidationError):
            match_vocab_value(vocab=vocab, param_name="p", value="display")


# ===========================================================================
# 3. Parameter specs edge cases
# ===========================================================================


class TestExtractParamSpecsEdgeCases:
    def test_falsy_candidates_skipped(self) -> None:
        """Empty list, empty dict, None values should be skipped."""
        payload = {
            "parameters": [],  # falsy
            "paramMap": {},  # falsy
            "searchConfig": {"parameters": [{"name": "p1", "type": "string"}]},
        }
        specs = extract_param_specs(payload)
        assert len(specs) == 1
        assert specs[0]["name"] == "p1"

    def test_non_dict_search_config(self) -> None:
        """searchConfig that isn't a dict should be handled."""
        payload = {"searchConfig": "not_a_dict"}
        specs = extract_param_specs(payload)
        assert specs == []


class TestAdaptParamSpecsEdgeCases:
    def test_zero_max_selected(self) -> None:
        """maxSelectedCount=0 should be kept (it's >= 0, not negative)."""
        payload = {
            "parameters": [
                {"name": "p1", "type": "multi-pick-vocabulary", "maxSelectedCount": 0}
            ]
        }
        specs = adapt_param_specs(payload)
        assert specs["p1"].max_selected_count == 0

    def test_float_min_selected_ignored(self) -> None:
        """Float minSelectedCount should be treated as non-int -> None."""
        payload = {
            "parameters": [{"name": "p1", "type": "string", "minSelectedCount": 1.5}]
        }
        specs = adapt_param_specs(payload)
        assert specs["p1"].min_selected_count is None

    def test_bool_allow_empty_truthy(self) -> None:
        """allowEmptyValue as truthy non-bool (int 1) should be treated as truthy."""
        payload = {
            "parameters": [{"name": "p1", "type": "string", "allowEmptyValue": 1}]
        }
        specs = adapt_param_specs(payload)
        assert specs["p1"].allow_empty_value is True

    def test_allow_empty_value_zero_is_false(self) -> None:
        """allowEmptyValue=0 should be falsy."""
        payload = {
            "parameters": [{"name": "p1", "type": "string", "allowEmptyValue": 0}]
        }
        specs = adapt_param_specs(payload)
        assert specs["p1"].allow_empty_value is False

    def test_duplicate_param_names_last_wins(self) -> None:
        """If multiple params have same name, last one wins in the dict."""
        payload = {
            "parameters": [
                {"name": "p1", "type": "string"},
                {"name": "p1", "type": "number"},
            ]
        }
        specs = adapt_param_specs(payload)
        assert specs["p1"].param_type == "number"


class TestFindMissingRequiredParamsEdgeCases:
    def test_multi_pick_with_non_empty_json_string(self) -> None:
        """Non-empty JSON array string should not be flagged as missing."""
        specs = [
            {"name": "p1", "type": "multi-pick-vocabulary", "allowEmptyValue": False}
        ]
        missing = find_missing_required_params(specs, {"p1": '["Plasmodium"]'})
        assert missing == []

    def test_multi_pick_with_none_value(self) -> None:
        specs = [
            {"name": "p1", "type": "multi-pick-vocabulary", "allowEmptyValue": False}
        ]
        missing = find_missing_required_params(specs, {"p1": None})
        assert missing == ["p1"]

    def test_multi_pick_with_empty_string(self) -> None:
        specs = [
            {"name": "p1", "type": "multi-pick-vocabulary", "allowEmptyValue": False}
        ]
        missing = find_missing_required_params(specs, {"p1": ""})
        assert missing == ["p1"]

    def test_value_is_zero(self) -> None:
        """Zero is falsy but should NOT be treated as missing for non-multi-pick."""
        specs = [{"name": "p1", "type": "number", "allowEmptyValue": False}]
        missing = find_missing_required_params(specs, {"p1": 0})
        # 0 is not in (None, "", [], {})
        assert missing == []

    def test_value_is_false(self) -> None:
        """Boolean False should NOT be treated as missing."""
        specs = [{"name": "p1", "type": "string", "allowEmptyValue": False}]
        missing = find_missing_required_params(specs, {"p1": False})
        # False is not in (None, "", [], {})
        assert missing == []

    def test_type_case_insensitive(self) -> None:
        """Type comparison uses .lower() so 'Multi-Pick-Vocabulary' works."""
        specs = [
            {"name": "p1", "type": "Multi-Pick-Vocabulary", "allowEmptyValue": False}
        ]
        missing = find_missing_required_params(specs, {"p1": "[]"})
        assert missing == ["p1"]


# ===========================================================================
# 4. Value helper function edge cases
# ===========================================================================


class TestValueHelperEdgeCases:
    def test_stringify_large_number(self) -> None:
        assert stringify(10**20) == str(10**20)

    def test_stringify_negative_number(self) -> None:
        assert stringify(-42) == "-42"

    def test_stringify_float_precision(self) -> None:
        """Float stringification should work normally."""
        result = stringify(0.1 + 0.2)
        # Python's str(0.30000000000000004) gives "0.30000000000000004"
        assert result.startswith("0.3")

    def test_validate_multi_count_max_zero(self) -> None:
        """max_selected=0 means no values are allowed."""
        spec = make_param_spec(ParamSpecConfig(max_selected=0))
        with pytest.raises(ValidationError):
            validate_multi_count(spec, ["a"])

    def test_validate_multi_count_max_zero_empty_list(self) -> None:
        """max_selected=0 with empty list should pass."""
        spec = make_param_spec(ParamSpecConfig(max_selected=0, min_selected=0))
        validate_multi_count(spec, [])

    def test_handle_empty_non_vocab_with_none_value_raises(self) -> None:
        """Non-vocab type with None value should raise when allow_empty is False."""
        spec = make_param_spec(ParamSpecConfig(param_type="number", allow_empty=False))
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_handle_empty_allows_all_types(self) -> None:
        """When allow_empty is True, always returns '' regardless of param_type."""
        for pt in ["string", "number", "multi-pick-vocabulary", "filter"]:
            spec = make_param_spec(ParamSpecConfig(param_type=pt, allow_empty=True))
            assert handle_empty(spec, "anything") == ""


# ===========================================================================
# 5. Canonicalizer edge cases
# ===========================================================================


class TestCanonicalizerEdgeCases:
    def test_multi_pick_with_duplicates(self) -> None:
        """Duplicate values in multi-pick should be preserved (no dedup by default)."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                vocabulary=[["a", "A"], ["b", "B"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["A", "A", "B"]})
        # Duplicates are kept because there's no dedup in the multi-pick path
        # (dedup only happens in _enforce_leaf_values)
        assert result["p"] == ["a", "a", "b"]

    def test_multi_pick_empty_list(self) -> None:
        """Empty list for multi-pick with allow_empty should return empty string."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                allow_empty=True,
            )
        )
        c = _canonicalizer(spec)
        # Empty list -> decode_values returns [] -> values is [] ->
        # No FAKE_ALL check -> _enforce_leaf (skip if not count_only_leaves) ->
        # validate_multi_count: empty with allow_empty passes
        # Returns cast(JSONValue, []) which is []
        result = c.canonicalize({"p": []})
        assert result["p"] == []

    def test_multi_pick_empty_list_without_allow_empty(self) -> None:
        """Empty list for multi-pick without allow_empty should fail."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                min_selected=1,
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": []})
        assert "at least 1" in (exc_info.value.detail or "")

    def test_number_range_with_list_of_one(self) -> None:
        """List with one element is not a valid range."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number-range"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": [42]})
        assert "must be a range" in (exc_info.value.detail or "")

    def test_number_range_with_empty_list(self) -> None:
        """Empty list is not a valid range."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number-range"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": []})
        assert "must be a range" in (exc_info.value.detail or "")

    def test_number_range_set_value_raises(self) -> None:
        """Set is not a valid range type."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number-range"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": {1, 10}})
        assert "must be a range" in (exc_info.value.detail or "")

    def test_input_dataset_empty_list_raises(self) -> None:
        """Empty list for input-dataset should raise."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="input-dataset"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": []})
        assert "single value" in (exc_info.value.detail or "")

    def test_filter_none_value_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="p", param_type="filter", allow_empty=True)
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": None})
        assert result["p"] == ""

    def test_unknown_param_type_preserves_value(self) -> None:
        """Unknown param types should preserve values as-is."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="totally_unknown"))
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": {"complex": [1, 2]}})
        assert result["p"] == {"complex": [1, 2]}

    def test_none_value_for_unknown_type(self) -> None:
        """None value for unknown type goes through _handle_empty."""
        spec = make_param_spec(
            ParamSpecConfig(name="p", param_type="totally_unknown", allow_empty=True)
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": None})
        assert result["p"] == ""

    def test_single_pick_with_json_array_string(self) -> None:
        """Single-pick with a JSON array string of one element should work."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="single-pick-vocabulary",
                vocabulary=[["val", "Display"]],
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": '["Display"]'})
        assert result["p"] == "val"

    def test_tuple_scalar_raises_for_number(self) -> None:
        """Tuple is rejected for scalar types."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": (1, 2)})
        assert "scalar" in (exc_info.value.detail or "")

    def test_set_scalar_raises_for_string(self) -> None:
        """Set is rejected for scalar types."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="string"))
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": {"a", "b"}})
        assert "scalar" in (exc_info.value.detail or "")


# ===========================================================================
# 6. Normalizer edge cases
# ===========================================================================


class TestNormalizerEdgeCases:
    def test_multi_pick_empty_list_with_allow_empty(self) -> None:
        """Empty list produces JSON '[]' which is valid for allow_empty."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                allow_empty=True,
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"p": []})
        assert result["p"] == json.dumps([])

    def test_multi_pick_single_value_string(self) -> None:
        """Single string value should be decoded and normalized."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                vocabulary=[["val", "Display"]],
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"p": "Display"})
        assert result["p"] == json.dumps(["val"])

    def test_range_tuple_produces_json_string(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number-range"))
        n = _normalizer(spec)
        result = n.normalize({"p": (5, 15)})
        parsed = json.loads(result["p"])
        assert parsed == {"min": 5, "max": 15}

    def test_filter_string_passthrough(self) -> None:
        """String filter values pass through as-is (not JSON-encoded)."""
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="filter"))
        n = _normalizer(spec)
        result = n.normalize({"p": "already_a_string"})
        assert result["p"] == "already_a_string"

    def test_unknown_type_passthrough(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="mystery"))
        n = _normalizer(spec)
        result = n.normalize({"p": [1, 2, 3]})
        assert result["p"] == [1, 2, 3]

    def test_number_range_invalid_string_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number-range"))
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": "not a range"})
        assert "must be a range" in (exc_info.value.detail or "")

    def test_input_dataset_none_value_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="p", param_type="input-dataset", allow_empty=True)
        )
        n = _normalizer(spec)
        result = n.normalize({"p": None})
        assert result["p"] == ""

    def test_single_pick_none_with_allow_empty(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="single-pick-vocabulary",
                allow_empty=True,
            )
        )
        n = _normalizer(spec)
        result = n.normalize({"p": None})
        assert result["p"] == ""


# ===========================================================================
# 7. Leaf enforcement edge cases (canonicalizer)
# ===========================================================================


class TestLeafEnforcementEdgeCases:
    @staticmethod
    def _deep_tree() -> dict:
        """4-level deep tree."""
        return {
            "data": {"term": "root", "display": "Root"},
            "children": [
                {
                    "data": {"term": "l1", "display": "Level 1"},
                    "children": [
                        {
                            "data": {"term": "l2", "display": "Level 2"},
                            "children": [
                                {
                                    "data": {"term": "l3_leaf", "display": "Deep Leaf"},
                                    "children": [],
                                },
                            ],
                        },
                    ],
                },
            ],
        }

    def test_deep_tree_leaf_expansion(self) -> None:
        """Selecting a top-level node should expand to the deepest leaf."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._deep_tree(),
            )
        )
        c = _canonicalizer(spec)
        result = c.canonicalize({"p": ["Root"]})
        assert result["p"] == ["l3_leaf"]

    def test_single_pick_leaf_enforcement_on_non_leaf(self) -> None:
        """Single-pick with count_only_leaves should reject non-leaf nodes."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="single-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=self._deep_tree(),
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": "Root"})
        assert "requires leaf" in (exc_info.value.detail or "")

    def test_leaf_enforcement_with_list_vocab(self) -> None:
        """List vocab should return empty from _expand_leaf_terms_for_match."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=[["a", "A"]],
            )
        )
        c = _canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": ["A"]})
        assert "requires leaf" in (exc_info.value.detail or "")

    def test_leaf_enforcement_with_none_vocab(self) -> None:
        """None vocab with count_only_leaves should not expand (empty result -> error)."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="multi-pick-vocabulary",
                count_only_leaves=True,
                vocabulary=None,
            )
        )
        c = _canonicalizer(spec)
        # vocab is None -> match_vocab_value returns value as-is
        # _enforce_leaf_values -> vocab is None -> _expand_leaf_terms_for_match
        # returns [] -> raises "requires leaf selections"
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": ["anything"]})
        assert "requires leaf" in (exc_info.value.detail or "")


# ===========================================================================
# 8. Normalizer vs Canonicalizer consistency
# ===========================================================================


class TestNormalizerVsCanonicalizerConsistency:
    """Verify both paths handle the same edge cases consistently."""

    def test_both_reject_unknown_params(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="known"))
        c = _canonicalizer(spec)
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"unknown": "val"})
        assert "does not exist" in (exc_info.value.detail or "")
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"unknown": "val"})
        assert "does not exist" in (exc_info.value.detail or "")

    def test_both_skip_input_step(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="step_id", param_type="input-step"))
        c = _canonicalizer(spec)
        n = _normalizer(spec)
        assert c.canonicalize({"step_id": "123"}) == {}
        assert n.normalize({"step_id": "123"}) == {}

    def test_both_handle_none_params(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p"))
        c = _canonicalizer(spec)
        n = _normalizer(spec)
        assert c.canonicalize(None) == {}
        assert n.normalize(None) == {}

    def test_both_reject_list_for_scalar(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="p", param_type="number"))
        c = _canonicalizer(spec)
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": [1, 2]})
        assert "scalar" in (exc_info.value.detail or "")
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": [1, 2]})
        assert "scalar" in (exc_info.value.detail or "")

    def test_both_reject_multiple_single_pick(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="p",
                param_type="single-pick-vocabulary",
                vocabulary=[["a", "A"], ["b", "B"]],
            )
        )
        c = _canonicalizer(spec)
        n = _normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            c.canonicalize({"p": ["A", "B"]})
        assert "only one value" in (exc_info.value.detail or "")
        with pytest.raises(ValidationError) as exc_info:
            n.normalize({"p": ["A", "B"]})
        assert "only one value" in (exc_info.value.detail or "")
