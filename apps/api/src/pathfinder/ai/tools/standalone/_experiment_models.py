"""Experiment tool response models and helpers."""

from __future__ import annotations

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONObject
from pydantic import Field

from pathfinder.services.wdk import get_results_api


class DownloadLinks(CamelModel):
    """Download links for export results."""

    json_url: str | None = None
    csv_url: str | None = None
    expires_in_seconds: int | None = None


class StepControlTestResult(CamelModel):
    """Result of a step-level control test."""

    step_id: int
    estimated_size: int = 0
    positive_intersection: int | None = None
    positive_controls_count: int | None = None
    positive_recall: float | None = None
    positive_intersection_ids: list[str] = Field(default_factory=list)
    positive_missing_ids: list[str] = Field(default_factory=list)
    negative_intersection: int | None = None
    negative_controls_count: int | None = None
    negative_false_positive_rate: float | None = None
    negative_intersection_ids: list[str] = Field(default_factory=list)
    downloads: DownloadLinks | None = None


class SearchControlTestResult(CamelModel):
    """Result of a search-level control test."""

    search_name: str = ""
    parameters: JSONObject = Field(default_factory=dict)
    estimated_size: int = 0
    positive_intersection: int | None = None
    positive_controls_count: int | None = None
    positive_recall: float | None = None
    positive_intersection_ids: list[str] = Field(default_factory=list)
    positive_missing_ids: list[str] = Field(default_factory=list)
    negative_intersection: int | None = None
    negative_controls_count: int | None = None
    negative_false_positive_rate: float | None = None
    negative_intersection_ids: list[str] = Field(default_factory=list)
    downloads: DownloadLinks | None = None


async def _run_step_control_tests(
    site_id: str,
    wdk_step_id: int,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> StepControlTestResult:
    """Run control tests against an already-built step using set intersection."""
    results_api = get_results_api(site_id)
    answer = await results_api.get_step_preview(wdk_step_id, limit=50000)
    result_ids = {r.display_name for r in answer.records}
    estimated_size = answer.meta.records_returned()

    result = StepControlTestResult(
        step_id=wdk_step_id,
        estimated_size=estimated_size,
    )

    if positive_controls:
        pos_set = set(positive_controls)
        intersection = result_ids & pos_set
        missing = pos_set - result_ids
        result.positive_intersection = len(intersection)
        result.positive_controls_count = len(pos_set)
        result.positive_recall = len(intersection) / len(pos_set) if pos_set else 0.0
        result.positive_intersection_ids = sorted(intersection)[:20]
        result.positive_missing_ids = sorted(missing)[:20]

    if negative_controls:
        neg_set = set(negative_controls)
        intersection = result_ids & neg_set
        result.negative_intersection = len(intersection)
        result.negative_controls_count = len(neg_set)
        result.negative_false_positive_rate = (
            len(intersection) / len(neg_set) if neg_set else 0.0
        )
        result.negative_intersection_ids = sorted(intersection)[:20]

    return result
