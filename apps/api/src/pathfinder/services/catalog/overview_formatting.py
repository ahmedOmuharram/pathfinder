"""Formats WDK search parameters into a required/optional overview."""

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import (
    FilterFieldInfo,
    ParameterInfo,
)
from pathfinder.services.catalog.param_sheet import build_sheet


class ParamOverviewEntry(CamelModel):
    """One parameter in a search overview, with the values it accepts."""

    name: str
    display_name: str
    type: str
    description: str
    value_format: str
    default: str | None = None
    min: float | None = None
    max: float | None = None
    vocabulary: list[VocabOption] = Field(default_factory=list)
    vocabulary_total: int = 0
    vocabulary_note: str | None = None
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


def _build_dependency_section(
    infos: list[ParameterInfo],
) -> dict[str, DependencyEntry]:
    """Name the parents each visible dependent parameter is read under.

    A hidden parameter is absent from the overview, so naming it here sends the
    model after a parameter it cannot see.
    """
    return {
        info.name: DependencyEntry(
            depends_on=info.vocab_depends_on,
            instruction=(
                f"Set {', '.join(info.vocab_depends_on)} first, then call "
                "get_parameter_options(...)"
            ),
        )
        for info in infos
        if info.vocab_depends_on and info.is_visible
    }


def format_search_overview(
    *,
    search_name: str,
    display_name: str,
    description: str,
    record_type: str,
    infos: list[ParameterInfo],
    query: str,
) -> SearchOverviewResult:
    """Split the parameters into required and optional entries with their values.

    Hidden parameters are excluded. ``query`` ranks a vocabulary too large to
    travel whole.
    """
    by_name = {info.name: info for info in infos}
    required: list[ParamOverviewEntry] = []
    optional: list[ParamOverviewEntry] = []

    for sheet in build_sheet(infos, query=query):
        info = by_name[sheet.name]
        entry = ParamOverviewEntry(
            name=sheet.name,
            display_name=sheet.display_name or sheet.name,
            type=sheet.type,
            description=sheet.help,
            value_format=info.value_format,
            default=sheet.default,
            min=sheet.min,
            max=sheet.max,
            vocabulary=sheet.vocabulary,
            vocabulary_total=sheet.vocabulary_total,
            vocabulary_note=sheet.vocabulary_note,
            controls_vocab_of=info.controls_vocab_of,
            filter_facets=sheet.filter_facets,
        )
        if sheet.required:
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
        dependencies=_build_dependency_section(infos),
    )
