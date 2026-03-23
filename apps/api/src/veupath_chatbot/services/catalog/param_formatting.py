"""Parameter spec formatting and annotation.

Pure module (no I/O). Transforms raw WDK parameter specs into
formatted info dicts for AI tool consumption, including dependency
annotation and vocabulary rendering.
"""

from typing import cast

from veupath_chatbot.integrations.veupathdb.wdk_parameters import (
    WDKBaseParameter,
    WDKEnumParam,
    WDKParameter,
)
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.catalog.vocab_rendering import (
    allowed_values,
    render_vocab_tree,
)

_PHYLETIC_STRUCTURAL_PARAMS = frozenset({"phyletic_indent_map", "phyletic_term_map"})

_PROFILE_PATTERN_HELP = (
    "Phylogenetic profile pattern. Format: %CODE:STATE[:QUANTIFIER]% (percent-delimited).\n"
    "  CODE  = species or group code from lookup_phyletic_codes()\n"
    "  STATE = Y (present) or N (absent)\n"
    "  QUANTIFIER = 'any' or 'all' (optional, only matters for group codes)\n"
    "\n"
    "For leaf species codes (e.g. pfal, hsap), quantifier is ignored:\n"
    "  pfal:Y  → present in P. falciparum\n"
    "  hsap:N  → absent from H. sapiens\n"
    "\n"
    "For group codes (e.g. MAMM, APIC), quantifier controls expansion:\n"
    "  MAMM:N       → absent from ALL mammals (default for :N)\n"
    "  MAMM:N:all   → same as above (explicit)\n"
    "  APIC:Y:any   → present in ANY Apicomplexa (default for :Y, dropped from pattern)\n"
    "  APIC:Y:all   → present in ALL Apicomplexa (expanded, usually 0 results)\n"
    "\n"
    "Example: '%MAMM:N%pfal:Y%' → P.falciparum present, all mammals absent\n"
    "\n"
    "CRITICAL: The 'organism' parameter controls which organisms' genes appear in "
    "results. You MUST select ALL relevant organisms (use all leaf values from the "
    "organism vocabulary tree, or use the tree's root '@@fake@@' sentinel for 'select all'). "
    "If you only select one organism, you will get 0 results even if the pattern is correct."
)


# ---------------------------------------------------------------------------
# Typed API (accepts list[WDKParameter])
# ---------------------------------------------------------------------------


def _build_typed_dependency_map(
    params: list[WDKParameter],
) -> dict[str, list[str]]:
    """Build ``depends_on`` map from typed WDK parameters.

    Returns ``depends_on[child]`` = list of parent param names whose values
    determine this child's vocabulary.
    """
    depends_on: dict[str, list[str]] = {}
    for param in params:
        base: WDKBaseParameter = param
        if base.dependent_params:
            for dep in base.dependent_params:
                depends_on.setdefault(dep, []).append(base.name)
    return depends_on


def _build_typed_controls_map(
    params: list[WDKParameter],
) -> dict[str, list[str]]:
    """Build ``controls`` map from typed WDK parameters.

    Returns ``controls[parent]`` = list of child param names whose vocabulary
    depends on this parent.
    """
    controls: dict[str, list[str]] = {}
    for param in params:
        base: WDKBaseParameter = param
        if base.dependent_params:
            controls[base.name] = list(base.dependent_params)
    return controls


def _format_typed_param(
    param: WDKParameter,
    depends_on: dict[str, list[str]],
    controls: dict[str, list[str]],
) -> JSONObject:
    """Format a single typed WDK parameter into an AI-consumable info dict."""
    base: WDKBaseParameter = param
    name = base.name
    help_text = base.help or ""
    if name == "profile_pattern":
        help_text = _PROFILE_PATTERN_HELP

    info: JSONObject = {
        "name": name,
        "displayName": base.display_name or name,
        "type": base.type,
        "required": not base.allow_empty_value,
        "isVisible": base.is_visible,
        "help": help_text,
    }

    # Extract vocabulary from enum params.
    vocabulary: JSONValue = None
    if isinstance(param, WDKEnumParam):
        vocabulary = param.vocabulary

    if base.type == "multi-pick-vocabulary" and isinstance(vocabulary, dict):
        tree_lines = render_vocab_tree(vocabulary, max_lines=80)
        if tree_lines:
            info["allowedValues_tree"] = cast(
                "JSONValue",
                "\n".join(tree_lines)
                + "\n(Pass a parent node to auto-select all its children)",
            )
    elif vocabulary is not None:
        vocab_for_allowed = vocabulary if isinstance(vocabulary, (dict, list)) else None
        allowed_entries = allowed_values(vocab_for_allowed)
        if allowed_entries:
            info["allowedValues"] = cast("JSONValue", allowed_entries)

    if base.initial_display_value is not None:
        info["defaultValue"] = base.initial_display_value

    if name in controls:
        info["controlsVocabOf"] = cast("JSONValue", controls[name])
    if name in depends_on:
        parents = depends_on[name]
        info["vocabDependsOn"] = cast("JSONValue", parents)
        info["note"] = (
            f"The allowed values for this param change based on the value of "
            f"{', '.join(parents)}. The values shown here are for the default "
            f"context only. Use get_dependent_vocab(search_name, param_name='{name}', "
            f"context_values={{'{parents[0]}': '<your chosen value>'}}) to see "
            f"the full vocabulary after setting {parents[0]}."
        )

    return info


def format_param_info_typed(params: list[WDKParameter]) -> list[JSONObject]:
    """Format typed WDK parameters for LLM display.

    Typed equivalent of :func:`format_param_info`.  Accepts parsed
    ``WDKParameter`` models instead of raw JSON dicts, using attribute
    access for type safety.

    Phyletic structural params are filtered out.

    :param params: Typed WDK parameter models.
    :returns: Formatted parameter info dicts.
    """
    depends_on = _build_typed_dependency_map(params)
    controls = _build_typed_controls_map(params)
    return [
        _format_typed_param(p, depends_on, controls)
        for p in params
        if p.name not in _PHYLETIC_STRUCTURAL_PARAMS
    ]
