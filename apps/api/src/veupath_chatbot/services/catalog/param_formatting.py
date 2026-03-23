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
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
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


def _build_dependency_maps(
    param_specs: JSONArray,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build reverse dependency maps from raw WDK parameter specs.

    Returns ``(depends_on, controls)`` where:
    - ``depends_on[child]`` = list of parent param names whose values
      determine this child's vocabulary.
    - ``controls[parent]`` = list of child param names whose vocabulary
      depends on this parent.
    """
    depends_on: dict[str, list[str]] = {}
    controls: dict[str, list[str]] = {}
    for spec in param_specs:
        if not isinstance(spec, dict):
            continue
        parent_name_raw = spec.get("name")
        parent_name = str(parent_name_raw) if parent_name_raw else ""
        dep_params_raw = spec.get("dependentParams")
        dep_params = dep_params_raw if isinstance(dep_params_raw, list) else []
        if dep_params and parent_name:
            dep_strs = [str(d) for d in dep_params]
            controls[parent_name] = dep_strs
            for dep_str in dep_strs:
                depends_on.setdefault(dep_str, []).append(parent_name)
    return depends_on, controls


def _annotate_vocabulary(
    info: JSONObject,
    param_type: str,
    vocabulary: JSONObject | JSONArray | None,
) -> None:
    """Add vocabulary/allowedValues entries to a param info dict."""
    if param_type == "multi-pick-vocabulary" and isinstance(vocabulary, dict):
        tree_lines = render_vocab_tree(vocabulary, max_lines=80)
        if tree_lines:
            info["allowedValues_tree"] = cast(
                "JSONValue",
                "\n".join(tree_lines)
                + "\n(Pass a parent node to auto-select all its children)",
            )
    else:
        allowed_entries = allowed_values(vocabulary)
        if allowed_entries:
            info["allowedValues"] = cast("JSONValue", allowed_entries)


def _annotate_dependencies(
    info: JSONObject,
    name: str,
    depends_on: dict[str, list[str]],
    controls: dict[str, list[str]],
) -> None:
    """Add dependency annotations to a param info dict."""
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


def _format_single_param(
    spec: JSONObject,
    depends_on: dict[str, list[str]],
    controls: dict[str, list[str]],
) -> JSONObject | None:
    """Format a single WDK parameter spec into an AI-consumable info dict.

    Returns ``None`` when the spec should be skipped (missing name or
    phyletic structural param).
    """
    name_raw = spec.get("name")
    name = name_raw if isinstance(name_raw, str) else ""
    if not name or name in _PHYLETIC_STRUCTURAL_PARAMS:
        return None

    display_name_raw = spec.get("displayName")
    display_name = display_name_raw if isinstance(display_name_raw, str) else name
    type_raw = spec.get("type")
    param_type = type_raw if isinstance(type_raw, str) else "string"
    help_raw = spec.get("help")
    help_text = (
        _PROFILE_PATTERN_HELP
        if name == "profile_pattern"
        else (help_raw if isinstance(help_raw, str) else "")
    )
    is_visible_raw = spec.get("isVisible")

    info: JSONObject = {
        "name": name,
        "displayName": display_name,
        "type": param_type,
        "required": not bool(spec.get("allowEmptyValue")),
        "isVisible": is_visible_raw if isinstance(is_visible_raw, bool) else True,
        "help": help_text,
    }

    vocabulary_raw = spec.get("vocabulary")
    vocabulary = vocabulary_raw if isinstance(vocabulary_raw, (dict, list)) else None
    _annotate_vocabulary(info, param_type, vocabulary)

    initial_display_raw = spec.get("initialDisplayValue")
    if initial_display_raw is not None:
        info["defaultValue"] = initial_display_raw
    default_value_raw = spec.get("defaultValue")
    if default_value_raw is not None and "defaultValue" not in info:
        info["defaultValue"] = default_value_raw

    _annotate_dependencies(info, name, depends_on, controls)
    return info


def format_param_info(param_specs: JSONArray) -> JSONArray:
    """Build a formatted parameter info array from raw WDK param specs.

    Each spec dict is transformed into a normalized info dict with keys:
    name, displayName, type, required, isVisible, help, and optionally
    allowedValues and defaultValue.

    Phyletic structural params (phyletic_indent_map, phyletic_term_map) are
    omitted from AI tool output — the model should never set them directly.
    The profile_pattern param gets enriched help text with encoding docs.

    :param param_specs: Raw parameter spec dicts from WDK.
    :returns: Formatted parameter info array.
    """
    depends_on, controls = _build_dependency_maps(param_specs)

    param_info: JSONArray = []
    for spec in param_specs:
        if not isinstance(spec, dict):
            continue
        info = _format_single_param(spec, depends_on, controls)
        if info is not None:
            param_info.append(info)
    return param_info


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
