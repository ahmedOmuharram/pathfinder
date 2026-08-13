"""Formats WDK search parameters into a required/optional overview. Pure, no I/O."""

from pydantic import Field, JsonValue

from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKBaseParameter,
    WDKParameter,
)
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    _value_format,
    filter_fields_for,
)
from pathfinder.services.catalog.vocab_rendering import allowed_values

_PHYLETIC_STRUCTURAL_PARAMS = frozenset({"phyletic_indent_map", "phyletic_term_map"})


class ParamOverviewEntry(CamelModel):
    """One parameter in a search overview."""

    name: str
    display_name: str
    type: str
    description: str
    has_vocabulary: bool
    value_format: str
    default: JsonValue | None = None
    min: float | None = None
    max: float | None = None
    vocab_summary: str | None = None
    controls_vocab_of: list[str] | None = None
    filter_facets: list[FilterFieldInfo] = Field(default_factory=list)


class DependencyEntry(CamelModel):
    """Dependency info for a single dependent parameter."""

    depends_on: list[str]
    instruction: str


class SearchOverviewResult(CamelModel):
    """Complete search overview for LLM consumption."""

    search_name: str
    display_name: str
    description: str
    record_type: str
    required: list[ParamOverviewEntry] = Field(default_factory=list)
    optional: list[ParamOverviewEntry] = Field(default_factory=list)
    dependencies: dict[str, DependencyEntry] = Field(default_factory=dict)


def _is_required(param: WDKBaseParameter) -> bool:
    """A parameter is required when it forbids an empty value or needs one selection."""
    if param.min_selected_count >= 1:
        return True
    return not param.allow_empty_value


def _build_dependency_maps(
    params: list[WDKParameter],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Map each parent to the children it controls, and each child to its parents."""
    controls: dict[str, list[str]] = {}
    depends_on: dict[str, list[str]] = {}
    for param in params:
        base: WDKBaseParameter = param
        if base.dependent_params:
            controls[base.name] = list(base.dependent_params)
            for dep in base.dependent_params:
                depends_on.setdefault(dep, []).append(base.name)
    return controls, depends_on


def _vocab_summary(param: WDKBaseParameter) -> str | None:
    """Summarize a vocabulary as a size and its first entry. None if there is no vocabulary."""
    entries = allowed_values(param.vocabulary)
    if not entries:
        return None
    count = len(entries)
    first_display = entries[0].display or entries[0].value
    return f"{count} values. Top: {first_display}"


def _has_vocabulary(param: WDKBaseParameter) -> bool:
    """Check if a parameter has a non-empty vocabulary."""
    return bool(allowed_values(param.vocabulary))


def _format_param_overview(
    param: WDKParameter,
    controls: dict[str, list[str]],
) -> ParamOverviewEntry:
    """Format one WDK parameter into a typed overview entry."""
    return ParamOverviewEntry(
        name=param.name,
        display_name=param.display_name or param.name,
        type=param.type,
        description=param.help or "",
        has_vocabulary=_has_vocabulary(param),
        value_format=_value_format(param.type),
        default=param.initial_display_value,
        min=param.min,
        max=param.max,
        vocab_summary=_vocab_summary(param),
        controls_vocab_of=controls.get(param.name),
        filter_facets=filter_fields_for(param),
    )


def _build_dependency_section(
    params: list[WDKParameter],
    depends_on: dict[str, list[str]],
) -> dict[str, DependencyEntry]:
    """Build the top-level dependencies section of the overview."""
    dependencies: dict[str, DependencyEntry] = {}
    param_names = {p.name for p in params}
    for child_name, parents in depends_on.items():
        if child_name not in param_names:
            continue
        dependencies[child_name] = DependencyEntry(
            depends_on=parents,
            instruction=(
                f"Set {', '.join(parents)} first, then call get_parameter_options(...)"
            ),
        )
    return dependencies


def format_search_overview(
    *,
    search_name: str,
    display_name: str,
    description: str,
    record_type: str,
    params: list[WDKParameter],
) -> SearchOverviewResult:
    """Split WDK parameters into required and optional entries with their dependencies.

    Hidden parameters and phyletic structural parameters are excluded.
    """
    controls, depends_on = _build_dependency_maps(params)

    required: list[ParamOverviewEntry] = []
    optional: list[ParamOverviewEntry] = []

    for param in params:
        base: WDKBaseParameter = param
        if not base.is_visible:
            continue
        if base.name in _PHYLETIC_STRUCTURAL_PARAMS:
            continue

        entry = _format_param_overview(param, controls)

        if _is_required(base):
            required.append(entry)
        else:
            optional.append(entry)

    return SearchOverviewResult(
        search_name=search_name,
        display_name=display_name,
        description=description,
        record_type=record_type,
        required=required,
        optional=optional,
        dependencies=_build_dependency_section(params, depends_on),
    )
