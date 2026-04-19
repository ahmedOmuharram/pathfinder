"""Typed response models for step-result browsing endpoints."""

from typing import Literal

from pydantic import ConfigDict, Field, JsonValue

from pathfinder.integrations.veupathdb.wdk_models import (
    WDKHistogramBin,
    WDKHistogramStatistics,
)
from pathfinder.platform.pydantic_base import CamelModel


class RecordAttribute(CamelModel):
    name: str
    display_name: str = ""
    help: str | None = None
    type: str | None = None
    is_displayable: bool = True
    is_sortable: bool = False
    is_suggested: bool = False


class AttributesResponse(CamelModel):
    attributes: list[RecordAttribute]
    record_type: str


class ClassifiedRecord(CamelModel):
    """WDK record plus optional TP/FP/FN/TN tag from experiment classification."""

    model_config = ConfigDict(populate_by_name=True)

    display_name: str = ""
    id: list[dict[str, str]] = Field(default_factory=list)
    record_class_name: str = ""
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    tables: dict[str, JsonValue] = Field(default_factory=dict)
    table_errors: list[str] = Field(default_factory=list)
    classification: Literal["TP", "FP", "FN", "TN"] | None = Field(
        default=None, alias="_classification",
    )


class RecordsPagination(CamelModel):
    offset: int
    num_records: int


class RecordsMeta(CamelModel):
    total_count: int
    display_total_count: int
    response_count: int
    pagination: RecordsPagination
    attributes: list[str]
    tables: list[str]


class RecordsResponse(CamelModel):
    records: list[ClassifiedRecord]
    meta: RecordsMeta


class RecordDetailResponse(CamelModel):
    display_name: str = ""
    id: list[dict[str, str]] = Field(default_factory=list)
    record_class_name: str = ""
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    attribute_names: dict[str, str] = Field(default_factory=dict)
    tables: dict[str, JsonValue] = Field(default_factory=dict)
    table_errors: list[str] = Field(default_factory=list)


class DistributionResponse(CamelModel):
    histogram: list[WDKHistogramBin]
    statistics: WDKHistogramStatistics
