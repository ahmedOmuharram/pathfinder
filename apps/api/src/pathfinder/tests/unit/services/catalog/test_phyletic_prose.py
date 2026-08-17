"""Every phyletic string the model reads says the pattern is derived.

The pattern is hidden and required. A string that still teaches its grammar
invites the model to write one by hand, which is the binding this contract
replaced.
"""

from __future__ import annotations

from pathfinder.ai.tools.standalone.catalog import lookup_phyletic_codes
from pathfinder.services.catalog.param_formatting import _PROFILE_PATTERN_HELP
from pathfinder.services.catalog.param_phyletic import LOOKUP_HINT

_DERIVED = "derived from"


def _normalized(text: str) -> str:
    return " ".join(text.split())


def test_the_hidden_parameter_help_says_it_is_derived() -> None:
    help_text = _normalized(_PROFILE_PATTERN_HELP)

    assert "It is DERIVED from included_species and excluded_species" in help_text
    assert "never write it" in help_text
    assert "QUANTIFIER" not in help_text


def test_the_lookup_tool_docstring_says_it_is_derived() -> None:
    doc = _normalized(lookup_phyletic_codes.__doc__ or "")

    assert _DERIVED in doc
    assert "included_species or excluded_species" in doc
    assert "never written by hand" in doc


def test_the_lookup_result_hint_says_it_is_derived() -> None:
    hint = _normalized(LOOKUP_HINT)

    assert "profile_pattern is derived from the two lists; never write it" in hint
    assert "included_species" in hint
    assert "excluded_species" in hint
