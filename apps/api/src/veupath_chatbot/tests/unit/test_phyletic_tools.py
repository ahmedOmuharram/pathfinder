"""Unit tests for phyletic profile tool additions.

Covers format_param_info behavior with phyletic structural params
(phyletic_indent_map, phyletic_term_map) and profile_pattern enrichment.
"""

from typing import Any

from veupath_chatbot.platform.types import JSONArray
from veupath_chatbot.services.catalog.param_formatting import format_param_info

# ---------------------------------------------------------------------------
# Shared test data — matches real WDK GenesByOrthologPattern param shapes
# ---------------------------------------------------------------------------

PHYLETIC_PARAMS: JSONArray = [
    {
        "name": "profile_pattern",
        "type": "string",
        "displayName": "Profile Pattern",
        "help": "Example: 'hsap=1T'",
        "allowEmptyValue": False,
        "isVisible": False,
    },
    {
        "name": "included_species",
        "type": "string",
        "displayName": "Included Species",
        "help": "",
        "allowEmptyValue": True,
        "isVisible": True,
    },
    {
        "name": "excluded_species",
        "type": "string",
        "displayName": "Excluded Species",
        "help": "",
        "allowEmptyValue": True,
        "isVisible": True,
    },
    {
        "name": "phyletic_indent_map",
        "type": "multi-pick-vocabulary",
        "displayName": "phyletic_indent_map",
        "help": "",
        "allowEmptyValue": True,
        "isVisible": False,
        "vocabulary": [["BACT", "1", None], ["FIRM", "2", None]],
    },
    {
        "name": "phyletic_term_map",
        "type": "multi-pick-vocabulary",
        "displayName": "phyletic_term_map",
        "help": "",
        "allowEmptyValue": True,
        "isVisible": False,
        "vocabulary": [["ALL", "Root", None], ["BACT", "Bacteria", None]],
    },
    {
        "name": "organism",
        "type": "multi-pick-vocabulary",
        "displayName": "Organism",
        "help": "",
        "allowEmptyValue": False,
        "isVisible": True,
    },
]


def _names(result: JSONArray) -> list[str]:
    """Extract parameter names from format_param_info output."""
    return [p["name"] for p in result if isinstance(p, dict)]


def _find_param(result: JSONArray, name: str) -> dict[str, Any]:
    """Find a parameter by name in format_param_info output."""
    for p in result:
        if isinstance(p, dict) and p.get("name") == name:
            return p
    msg = f"Parameter '{name}' not found in result"
    raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFormatParamInfoPhyleticFiltering:
    """format_param_info strips phyletic structural params from AI output."""

    def test_phyletic_indent_map_excluded(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        names = _names(result)
        assert "phyletic_indent_map" not in names

    def test_phyletic_term_map_excluded(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        names = _names(result)
        assert "phyletic_term_map" not in names

    def test_profile_pattern_still_present(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        names = _names(result)
        assert "profile_pattern" in names

    def test_included_species_passes_through(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        names = _names(result)
        assert "included_species" in names

    def test_excluded_species_passes_through(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        names = _names(result)
        assert "excluded_species" in names

    def test_organism_passes_through(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        names = _names(result)
        assert "organism" in names

    def test_result_count_excludes_structural(self) -> None:
        """6 input params minus 2 structural = 4 output params."""
        result = format_param_info(PHYLETIC_PARAMS)
        assert len(result) == 4


class TestFormatParamInfoProfilePatternHelp:
    """format_param_info enriches profile_pattern help text."""

    def test_profile_pattern_help_contains_encoding_example(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        pp = _find_param(result, "profile_pattern")
        assert "CODE:STATE" in pp["help"]

    def test_profile_pattern_help_mentions_lookup_tool(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        pp = _find_param(result, "profile_pattern")
        assert "lookup_phyletic_codes" in pp["help"]

    def test_profile_pattern_help_replaces_original(self) -> None:
        """Original help text ('Example: hsap=1T') is replaced, not appended."""
        result = format_param_info(PHYLETIC_PARAMS)
        pp = _find_param(result, "profile_pattern")
        assert pp["help"] != "Example: 'hsap=1T'"

    def test_profile_pattern_help_contains_exclude_example(self) -> None:
        result = format_param_info(PHYLETIC_PARAMS)
        pp = _find_param(result, "profile_pattern")
        assert "hsap:N" in pp["help"]


class TestFormatParamInfoNonPhyletic:
    """Non-phyletic params pass through format_param_info unchanged."""

    def test_non_phyletic_params_unaffected(self) -> None:
        """A search with no phyletic params formats normally (no side effects)."""
        normal_params: JSONArray = [
            {
                "name": "organism",
                "type": "multi-pick-vocabulary",
                "displayName": "Organism",
                "help": "Select organism",
                "allowEmptyValue": False,
                "isVisible": True,
            },
            {
                "name": "taxon",
                "type": "string",
                "displayName": "Taxon",
                "help": "Taxon filter",
                "allowEmptyValue": True,
                "isVisible": True,
            },
        ]
        result = format_param_info(normal_params)
        names = _names(result)
        assert names == ["organism", "taxon"]
        assert len(result) == 2

    def test_non_phyletic_help_preserved(self) -> None:
        """Help text for non-phyletic params is preserved as-is."""
        params: JSONArray = [
            {
                "name": "organism",
                "type": "multi-pick-vocabulary",
                "displayName": "Organism",
                "help": "Select organism",
                "allowEmptyValue": False,
                "isVisible": True,
            },
        ]
        result = format_param_info(params)
        assert result[0]["help"] == "Select organism"

    def test_empty_input_returns_empty(self) -> None:
        assert format_param_info([]) == []

    def test_skips_non_dict_entries(self) -> None:
        result = format_param_info(["not_a_dict", 42, None])
        assert result == []

    def test_skips_entries_without_name(self) -> None:
        result = format_param_info([{"type": "string", "help": "no name"}])
        assert result == []
