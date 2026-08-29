"""Return shapes of the EDA tools. Every field is something the model acts on."""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONObject
from pydantic import Field

from pathfinder.services.eda.description import EdaVariableOut, StudyDescription


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


class EdaFilterSheetEntry(EdaVariableOut):
    """One variable, with everything needed to write a filter for it.

    Only a filterable variable reaches the sheet, so ``filter_type`` is
    always set here.
    """

    entity_display_name: str = ""
    example: JSONObject = Field(default_factory=dict)


class EdaFiltersResult(CamelModel):
    """Result of one set_eda_filters call."""

    applied: bool = False
    analysis_id: str = ""
    dataset_id: str = ""
    num_filters: int = 0
    # Every filterable variable, with its type, its vocabulary and one example
    # filter object. Declared before ``filters_template`` so the sheet is read
    # before the shape to copy.
    decide: list[EdaFilterSheetEntry] = Field(default_factory=list)
    # The exact array shape to send back. Empty on the first call.
    filters_template: list[JSONObject] = Field(default_factory=list)
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
