"""Return shapes of the EDA tools. Every field is something the model acts on."""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONObject
from pydantic import Field, JsonValue, model_serializer
from pydantic_core.core_schema import SerializerFunctionWrapHandler

from pathfinder.services.eda.description import EdaFilterType, StudyDescription


class EdaStudyCardOut(CamelModel):
    dataset_id: str
    study_id: str
    display_name: str
    short_display_name: str = ""
    description: str = ""
    source_type: str = ""
    relevance: float = 0.0
    can_subset: bool = False
    can_export_rows: bool = False


class EdaStudySearchResult(CamelModel):
    studies: list[EdaStudyCardOut] = Field(default_factory=list)
    guidance: str = ""


class EdaStudyDescription(StudyDescription):
    """One study's shape, plus what the model should do with it."""

    guidance: str = ""


class EdaFilterSheetEntry(CamelModel):
    """One variable, with everything needed to write a filter for it.

    The sheet is read by a model, so a field a variable does not declare is
    not sent: the entity tree and the variable type it was derived from are
    read from ``describe_eda_study``.
    """

    entity_id: str
    entity_display_name: str = ""
    variable_id: str
    display_name: str
    filter_type: EdaFilterType
    is_multi_valued: bool = False
    vocabulary: list[str] = Field(default_factory=list)
    vocabulary_total: int = 0
    vocabulary_note: str | None = None
    range_min: float | None = None
    range_max: float | None = None
    date_min: str | None = None
    date_max: str | None = None
    sub_filter_variable_ids: list[str] = Field(default_factory=list)
    example: JSONObject = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _what_the_variable_declares(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, JsonValue]:
        """A field with no value says nothing, so it is not serialized."""
        dumped: dict[str, JsonValue] = handler(self)
        return {
            name: value
            for name, value in dumped.items()
            if value is not None and value not in ([], "", {})
        }


class EdaFiltersResult(CamelModel):
    """Result of one set_eda_filters call."""

    applied: bool = False
    analysis_id: str = ""
    dataset_id: str = ""
    num_filters: int = 0
    # Every filterable variable, with its type, its vocabulary and one example
    # filter object to copy.
    decide: list[EdaFilterSheetEntry] = Field(default_factory=list)
    filter_summaries: list[str] = Field(default_factory=list)
    guidance: str = ""


class EdaAnalysisOpened(CamelModel):
    """The analysis this conversation now edits."""

    analysis_id: str
    dataset_id: str
    study_id: str
    display_name: str = ""
    study_display_name: str = ""
    gene_entity_id: str | None = None
    can_export_rows: bool = False
    guidance: str = ""


class EdaSubsetPreviewResult(CamelModel):
    """What the open analysis's filters select on one entity."""

    entity_id: str
    entity_display_name: str = ""
    count: int = 0
    unfiltered_count: int = 0
    variable_id: str | None = None
    variable_display_name: str = ""
    is_multi_valued: bool = False
    labels: list[str] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    num_var_values: int = 0
    num_missing_cases: int = 0
    distribution_note: str | None = None
    guidance: str = ""
