"""Every recorded response validates against the model that reads it."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pathfinder.integrations.eda.models import (
    TABULAR_JSON,
    EdaAppsResponse,
    EdaComputeJob,
    EdaCountResponse,
    EdaDistributionResponse,
    EdaPermissionsResponse,
    EdaStudiesResponse,
    EdaStudyDetailResponse,
    VolcanoStatsResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"

READERS: dict[str, Callable[[object], object]] = {
    "studies_list.json": EdaStudiesResponse.model_validate,
    "study_detail_de.json": EdaStudyDetailResponse.model_validate,
    "study_detail_phenotype.json": EdaStudyDetailResponse.model_validate,
    "permissions.json": EdaPermissionsResponse.model_validate,
    "count_unfiltered.json": EdaCountResponse.model_validate,
    "count_filtered.json": EdaCountResponse.model_validate,
    "distribution_categorical.json": EdaDistributionResponse.model_validate,
    "tabular_json.json": TABULAR_JSON.validate_python,
    "apps.json": EdaAppsResponse.model_validate,
    "compute_job_lookup.json": EdaComputeJob.model_validate,
    "volcano_statistics.json": VolcanoStatsResponse.model_validate,
}


def test_every_fixture_file_has_a_reader() -> None:
    on_disk = {p.name for p in FIXTURES.glob("*.json")}
    assert on_disk == set(READERS)


@pytest.mark.parametrize("name", sorted(READERS))
def test_fixture_validates(name: str) -> None:
    raw = json.loads((FIXTURES / name).read_text())
    reader = READERS[name]
    reader(raw)
