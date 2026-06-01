"""Typed response models for step-result browsing endpoints."""

from typing import Literal

from pydantic import JsonValue

from pathfinder.domain.wdk_values import (
    WDKHistogramBin,
    WDKHistogramStatistics,
    WDKRecordIdPart,
)
from pathfinder.platform.pydantic_base import CamelModel


class ClassifiedRecord(CamelModel):
    """WDK record plus optional TP/FP/FN/TN tag from experiment classification."""

    display_name: str
    id: list[WDKRecordIdPart]
    record_class_name: str
    attributes: dict[str, JsonValue]
    tables: dict[str, JsonValue]
    table_errors: list[str]
    classification: Literal["TP", "FP", "FN", "TN"] | None = None


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


class DistributionResponse(CamelModel):
    histogram: list[WDKHistogramBin]
    statistics: WDKHistogramStatistics
