"""Tests for StrategyAPI base parameter normalization functions.

Verifies pure functions in strategy_api/base.py:
- _sort_profile_pattern(): OrthoMCL pattern sorting
- _normalize_parameters(): param normalization for WDK
- _parse_param_values(): JSON string → list
- _build_phyletic_tree(): indent vocab → parent/child/leaf sets
- _expand_entries(): group code expansion in profile_pattern
"""

from unittest.mock import AsyncMock

from veupath_chatbot.integrations.veupathdb.strategy_api.base import (
    StrategyAPIBase,
    _build_phyletic_tree,
    _expand_entries,
    _sort_profile_pattern,
)

# ── _sort_profile_pattern ────────────────────────────────────────


class TestSortProfilePattern:
    def test_sorts_entries_alphabetically(self) -> None:
        """OrthoMCL requires alphabetical ordering of pattern entries."""
        assert _sort_profile_pattern("%ZEBRA:Y%APPLE:Y%MOUSE:Y%") == (
            "%APPLE:Y%MOUSE:Y%ZEBRA:Y%"
        )

    def test_single_entry(self) -> None:
        assert _sort_profile_pattern("%PFAL:Y%") == "%PFAL:Y%"

    def test_already_sorted(self) -> None:
        assert _sort_profile_pattern("%A:Y%B:N%C:Y%") == "%A:Y%B:N%C:Y%"

    def test_not_pattern_format_unchanged(self) -> None:
        """Strings not starting/ending with % pass through unchanged."""
        assert _sort_profile_pattern("not a pattern") == "not a pattern"
        assert _sort_profile_pattern("%partial") == "%partial"
        assert _sort_profile_pattern("partial%") == "partial%"

    def test_empty_pattern_unchanged(self) -> None:
        assert _sort_profile_pattern("%%") == "%%"

    def test_entries_with_colons(self) -> None:
        """Entries like 'CODE:STATE:QUANTIFIER' should sort by full string."""
        result = _sort_profile_pattern("%Z:N:all%A:Y:any%M:Y%")
        assert result == "%A:Y:any%M:Y%Z:N:all%"


# ── StrategyAPIBase._normalize_parameters ─────────────────────────


class TestNormalizeParameters:
    """Tests for StrategyAPIBase._normalize_parameters()."""

    def _make_api(self) -> StrategyAPIBase:
        client = AsyncMock()
        return StrategyAPIBase(client=client, user_id="test_user")

    def test_none_values_omitted(self) -> None:
        api = self._make_api()
        result = api._normalize_parameters({"a": "val", "b": None})
        assert result == {"a": "val"}
        assert "b" not in result

    def test_string_values_preserved(self) -> None:
        api = self._make_api()
        result = api._normalize_parameters({"org": "Plasmodium falciparum"})
        assert result == {"org": "Plasmodium falciparum"}

    def test_empty_string_preserved_for_explicit_strings(self) -> None:
        """String values with empty string are kept because caller explicitly set them."""
        api = self._make_api()
        result = api._normalize_parameters({"bq_input_step": ""})
        assert result == {"bq_input_step": ""}

    def test_keep_empty_preserves_blank_param(self) -> None:
        api = self._make_api()
        result = api._normalize_parameters(
            {"bq_input_step": ""},
            keep_empty={"bq_input_step"},
        )
        assert result == {"bq_input_step": ""}

    def test_none_parameters_returns_empty(self) -> None:
        api = self._make_api()
        result = api._normalize_parameters(None)
        assert result == {}

    def test_profile_pattern_sorted(self) -> None:
        """profile_pattern entries should be sorted alphabetically."""
        api = self._make_api()
        result = api._normalize_parameters(
            {"profile_pattern": "%ZEBRA:Y%APPLE:Y%"}
        )
        assert result["profile_pattern"] == "%APPLE:Y%ZEBRA:Y%"


# ── StrategyAPIBase._parse_param_values ───────────────────────────


class TestParseParamValues:
    def _make_api(self) -> StrategyAPIBase:
        return StrategyAPIBase(client=AsyncMock(), user_id="test")

    def test_json_array_string(self) -> None:
        api = self._make_api()
        assert api._parse_param_values('["a", "b", "c"]') == ["a", "b", "c"]

    def test_plain_string_becomes_list(self) -> None:
        """Non-JSON string is wrapped in a list."""
        api = self._make_api()
        assert api._parse_param_values("plain_value") == ["plain_value"]

    def test_empty_string(self) -> None:
        api = self._make_api()
        assert api._parse_param_values("") == []

    def test_invalid_json_becomes_single_item(self) -> None:
        api = self._make_api()
        assert api._parse_param_values("[invalid") == ["[invalid"]

    def test_json_non_list_returns_empty(self) -> None:
        """JSON that parses to non-list (e.g. string) returns empty list."""
        api = self._make_api()
        assert api._parse_param_values('"just_a_string"') == []

    def test_json_object_returns_empty(self) -> None:
        api = self._make_api()
        assert api._parse_param_values('{"key": "value"}') == []


# ── _build_phyletic_tree ──────────────────────────────────────────


class TestBuildPhyleticTree:
    def test_flat_list(self) -> None:
        """All entries at same depth → all leaves, no children."""
        indent_vocab = [
            ["PFAL", 0],
            ["PVIV", 0],
            ["TGON", 0],
        ]
        children_of, leaf_codes = _build_phyletic_tree(indent_vocab)
        assert children_of == {}
        assert leaf_codes == {"PFAL", "PVIV", "TGON"}

    def test_parent_with_children(self) -> None:
        """Parent at depth 0, children at depth 1."""
        indent_vocab = [
            ["APICOMPLEXA", 0],
            ["PFAL", 1],
            ["PVIV", 1],
            ["TGON", 1],
        ]
        children_of, leaf_codes = _build_phyletic_tree(indent_vocab)
        assert "APICOMPLEXA" in children_of
        assert set(children_of["APICOMPLEXA"]) == {"PFAL", "PVIV", "TGON"}
        assert leaf_codes == {"PFAL", "PVIV", "TGON"}

    def test_nested_groups(self) -> None:
        """Multi-level hierarchy: group → subgroup → leaf."""
        indent_vocab = [
            ["ROOT", 0],
            ["GROUP_A", 1],
            ["LEAF_1", 2],
            ["LEAF_2", 2],
            ["GROUP_B", 1],
            ["LEAF_3", 2],
        ]
        children_of, leaf_codes = _build_phyletic_tree(indent_vocab)
        assert "ROOT" in children_of
        # ROOT's descendants include everything below it
        assert set(children_of["ROOT"]) == {
            "GROUP_A", "LEAF_1", "LEAF_2", "GROUP_B", "LEAF_3"
        }
        assert set(children_of["GROUP_A"]) == {"LEAF_1", "LEAF_2"}
        assert set(children_of["GROUP_B"]) == {"LEAF_3"}
        assert leaf_codes == {"LEAF_1", "LEAF_2", "LEAF_3"}

    def test_skips_non_list_entries(self) -> None:
        indent_vocab = ["bad", None, ["PFAL", 0]]
        _children_of, leaf_codes = _build_phyletic_tree(indent_vocab)
        assert leaf_codes == {"PFAL"}

    def test_empty_vocab(self) -> None:
        children_of, leaf_codes = _build_phyletic_tree([])
        assert children_of == {}
        assert leaf_codes == set()


# ── _expand_entries ───────────────────────────────────────────────


class TestExpandEntries:
    def test_leaf_code_passes_through(self) -> None:
        """Leaf codes are kept as-is (without quantifier)."""
        leaf_codes = {"PFAL", "PVIV"}
        children_of: dict[str, list[str]] = {}
        result = _expand_entries(["PFAL:Y"], children_of, leaf_codes)
        assert result == ["PFAL:Y"]

    def test_group_code_expanded_with_all_quantifier(self) -> None:
        """Group code with default quantifier for N (all) expands to all leaves."""
        children_of = {"MAMM": ["HUMAN", "MOUSE", "RAT"]}
        leaf_codes = {"HUMAN", "MOUSE", "RAT"}
        # N state → default quantifier is "all"
        result = _expand_entries(["MAMM:N"], children_of, leaf_codes)
        assert set(result) == {"HUMAN:N", "MOUSE:N", "RAT:N"}

    def test_group_code_any_quantifier_dropped(self) -> None:
        """'any' quantifier cannot be expressed in WDK profile_pattern."""
        children_of = {"MAMM": ["HUMAN", "MOUSE"]}
        leaf_codes = {"HUMAN", "MOUSE"}
        result = _expand_entries(["MAMM:Y:any"], children_of, leaf_codes)
        # "any" is unsupported → entry is dropped entirely
        assert result == []

    def test_group_code_all_quantifier_explicit(self) -> None:
        children_of = {"MAMM": ["HUMAN", "MOUSE"]}
        leaf_codes = {"HUMAN", "MOUSE"}
        result = _expand_entries(["MAMM:N:all"], children_of, leaf_codes)
        assert set(result) == {"HUMAN:N", "MOUSE:N"}

    def test_group_only_expands_leaf_descendants(self) -> None:
        """Group expansion should only include leaf codes, not sub-groups."""
        children_of = {"ROOT": ["SUB", "LEAF1"], "SUB": ["LEAF2", "LEAF3"]}
        leaf_codes = {"LEAF1", "LEAF2", "LEAF3"}
        result = _expand_entries(["ROOT:N:all"], children_of, leaf_codes)
        # Only direct leaf descendants of ROOT that are in leaf_codes
        assert "LEAF1:N" in result
        assert "SUB:N" not in result

    def test_entry_without_colon_passes_through(self) -> None:
        result = _expand_entries(["no_colon"], {}, set())
        assert result == ["no_colon"]

    def test_y_state_defaults_to_any(self) -> None:
        """Y state without explicit quantifier defaults to 'any' (dropped)."""
        children_of = {"MAMM": ["HUMAN", "MOUSE"]}
        leaf_codes = {"HUMAN", "MOUSE"}
        result = _expand_entries(["MAMM:Y"], children_of, leaf_codes)
        # Default for Y is "any", which is unsupported → dropped
        assert result == []

    def test_mixed_entries(self) -> None:
        children_of = {"MAMM": ["HUMAN", "MOUSE"]}
        leaf_codes = {"HUMAN", "MOUSE", "PFAL"}
        entries = ["PFAL:Y", "MAMM:N"]
        result = _expand_entries(entries, children_of, leaf_codes)
        assert result[0] == "PFAL:Y"  # leaf passes through
        assert "HUMAN:N" in result
        assert "MOUSE:N" in result

    def test_unknown_code_passes_through(self) -> None:
        """Code not in children_of treated as leaf."""
        result = _expand_entries(["UNKNOWN:Y"], {}, set())
        assert result == ["UNKNOWN:Y"]
