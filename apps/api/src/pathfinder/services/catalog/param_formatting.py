"""Parameter spec formatting and annotation.

Pure module (no I/O). Transforms raw WDK parameter specs into
formatted info dicts for AI tool consumption, including dependency
annotation and vocabulary rendering.
"""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.wdk_vocab import (
    VocabOption,
    WDKTreeBoxVocabNode,
    WDKVocabulary,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKParameter
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.vocab_rendering import (
    _MAX_VOCAB_ENTRIES,
    allowed_values,
    render_vocab_tree,
)

_PHYLETIC_STRUCTURAL_PARAMS = frozenset({"phyletic_indent_map", "phyletic_term_map"})


_VALUE_FORMAT_TEMPLATES: dict[str, str] = {
    "string": '{"type": "string", "value": "<your value>"}',
    "number": '{"type": "number", "value": <number>}',
    "number-range": '{"type": "number-range", "min": <number>, "max": <number>}',
    "date": '{"type": "date", "value": "<YYYY-MM-DD>"}',
    "date-range": '{"type": "date-range", "min": "<YYYY-MM-DD>", "max": "<YYYY-MM-DD>"}',
    "timestamp": '{"type": "timestamp", "value": "<ISO-8601>"}',
    "single-pick-vocabulary": '{"type": "single-pick-vocabulary", "value": "<one of allowed_values>"}',
    "multi-pick-vocabulary": '{"type": "multi-pick-vocabulary", "values": ["<from allowed_values>", "..."]}',
    "filter": '{"type": "filter", "filters": [{"field": "<field>", "value": <value>}]}',
    "input-dataset": '{"type": "input-dataset", "datasetId": "<id>"}',
    "input-step": '{"type": "input-step", "stepId": "<id>"}',
}


def _value_format(param_type: str) -> str:
    return _VALUE_FORMAT_TEMPLATES.get(
        param_type,
        '{"type": "string", "value": "<your value>"}',
    )


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


class ParameterInfo(CamelModel):
    """Formatted WDK parameter info for AI tool consumption."""

    kind: Literal["parameter_info"] = "parameter_info"
    name: str
    display_name: str
    type: str
    required: bool
    is_visible: bool
    help: str
    value_format: str
    default_value: str | None = None
    allowed_values: list[VocabOption] | None = None
    allowed_values_tree: str | None = None
    allowed_values_note: str | None = None
    controls_vocab_of: list[str] | None = None
    vocab_depends_on: list[str] | None = None
    note: str | None = None


class ParameterNotOnSearch(CamelModel):
    """Returned by ``get_parameter_options`` when ``parameter_id`` is not a
    valid parameter on ``search_name``. Carries the same did-you-mean
    info that ``ModelRetry`` used to raise — but as a normal tool return,
    so the call doesn't consume retry budget. The model self-corrects on
    its next call from this payload.
    """

    kind: Literal["parameter_not_on_search"] = "parameter_not_on_search"
    search_name: str
    requested_parameter_id: str
    message: str
    suggestions: list[str]
    valid_parameter_ids: list[str]


GetParameterOptionsResult = Annotated[
    ParameterInfo | ParameterNotOnSearch,
    Field(discriminator="kind"),
]


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
        if param.dependent_params:
            for dep in param.dependent_params:
                depends_on.setdefault(dep, []).append(param.name)
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
        if param.dependent_params:
            controls[param.name] = list(param.dependent_params)
    return controls


@dataclass(frozen=True)
class _VocabFields:
    allowed_values: list[VocabOption] | None = None
    allowed_values_tree: str | None = None
    allowed_values_note: str | None = None


def _format_vocabulary(param: WDKParameter) -> _VocabFields:
    return _format_vocabulary_raw(
        param_name=param.name,
        param_type=param.type,
        vocabulary=param.vocabulary,
    )


def _format_vocabulary_raw(
    *,
    param_name: str,
    param_type: str,
    vocabulary: WDKVocabulary | None,
) -> _VocabFields:
    if param_type == "multi-pick-vocabulary" and isinstance(
        vocabulary, WDKTreeBoxVocabNode
    ):
        tree_lines = render_vocab_tree(vocabulary, max_lines=80)
        if tree_lines:
            tree_text = "\n".join(tree_lines)
            truncated = any("use query=" in line for line in tree_lines)
            suffix = "\n(Pass a parent node to auto-select all its children)"
            if truncated:
                suffix += (
                    f"\nNote: tree truncated — use get_parameter_options("
                    f"search_name='<search>', parameter_id='{param_name}', "
                    f"query='<keyword>') to see values for a specific category."
                )
            return _VocabFields(allowed_values_tree=tree_text + suffix)
    elif vocabulary is not None:
        allowed_entries = allowed_values(vocabulary)
        if allowed_entries:
            note: str | None = None
            if len(allowed_entries) >= _MAX_VOCAB_ENTRIES:
                note = (
                    f"Showing first {_MAX_VOCAB_ENTRIES} of many values (list truncated). "
                    "Use the exact value/ID you need; it does not have to appear in this list."
                )
            return _VocabFields(
                allowed_values=allowed_entries, allowed_values_note=note
            )

    return _VocabFields()


def format_typed_param(
    param: WDKParameter,
    depends_on: dict[str, list[str]],
    controls: dict[str, list[str]],
) -> ParameterInfo:
    """Format a single typed WDK parameter into an AI-consumable info object."""
    name = param.name
    help_text = param.help or ""
    if name == "profile_pattern":
        help_text = _PROFILE_PATTERN_HELP

    vocab = _format_vocabulary(param)

    note: str | None = None
    vocab_depends_on: list[str] | None = None
    if name in depends_on:
        parents = depends_on[name]
        vocab_depends_on = parents
        note = (
            f"The allowed values for this param change based on the value of "
            f"{', '.join(parents)}. The values shown here are for the default "
            f"context only. Use get_parameter_options(search_name, parameter_id='{name}', "
            f"context_values={{'{parents[0]}': '<your chosen value>'}}) to see "
            f"the full vocabulary after setting {parents[0]}."
        )

    return ParameterInfo(
        name=name,
        display_name=param.display_name or name,
        type=param.type,
        required=not param.allow_empty_value,
        is_visible=param.is_visible,
        help=help_text,
        value_format=_value_format(param.type),
        default_value=param.initial_display_value,
        allowed_values=vocab.allowed_values,
        allowed_values_tree=vocab.allowed_values_tree,
        allowed_values_note=vocab.allowed_values_note,
        controls_vocab_of=controls.get(name),
        vocab_depends_on=vocab_depends_on,
        note=note,
    )


def format_normalized_param_info(
    specs: dict[str, ParamSpecNormalized],
) -> list[ParameterInfo]:
    depends_on: dict[str, list[str]] = {}
    controls: dict[str, list[str]] = {}
    for parent_name, parent_spec in specs.items():
        for child_name in parent_spec.dependent_params:
            depends_on.setdefault(child_name, []).append(parent_name)
            controls.setdefault(parent_name, []).append(child_name)

    return [
        _format_normalized_one(spec, depends_on, controls)
        for name, spec in specs.items()
        if name not in _PHYLETIC_STRUCTURAL_PARAMS
    ]


def _format_normalized_one(
    spec: ParamSpecNormalized,
    depends_on: dict[str, list[str]],
    controls: dict[str, list[str]],
) -> ParameterInfo:
    vocab = _format_vocabulary_raw(
        param_name=spec.name,
        param_type=spec.param_type,
        vocabulary=spec.vocabulary,
    )
    is_required = not spec.allow_empty_value or (
        spec.min_selected_count is not None and spec.min_selected_count >= 1
    )
    return ParameterInfo(
        name=spec.name,
        display_name=spec.name,
        type=spec.param_type,
        required=is_required,
        is_visible=spec.is_visible,
        help=spec.help or "",
        value_format=_value_format(spec.param_type),
        default_value=spec.initial_display_value,
        allowed_values=vocab.allowed_values,
        allowed_values_tree=vocab.allowed_values_tree,
        allowed_values_note=vocab.allowed_values_note,
        controls_vocab_of=controls.get(spec.name),
        vocab_depends_on=depends_on.get(spec.name),
    )


def format_param_info_typed(params: list[WDKParameter]) -> list[ParameterInfo]:
    """Format typed WDK parameters for LLM display.

    Typed equivalent of :func:`format_param_info`.  Accepts parsed
    ``WDKParameter`` models instead of raw JSON dicts, using attribute
    access for type safety.

    Phyletic structural params are filtered out.

    :param params: Typed WDK parameter models.
    :returns: Formatted parameter info objects.
    """
    depends_on = _build_typed_dependency_map(params)
    controls = _build_typed_controls_map(params)
    return [
        format_typed_param(p, depends_on, controls)
        for p in params
        if p.name not in _PHYLETIC_STRUCTURAL_PARAMS
    ]
