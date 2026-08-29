from __future__ import annotations

import json
from pathlib import Path

from pathfinder.integrations.eda.models import (
    EdaPermissionsResponse,
    EdaStudiesResponse,
    EdaStudyOverview,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_study_overview_tolerates_a_missing_short_display_name() -> None:
    """shortDisplayName and description are declared required and are absent live."""
    overview = EdaStudyOverview.model_validate(
        {
            "id": "STUDY_ccab256dfb",
            "datasetId": "DS_ccab256dfb",
            "sha1hash": "ccab256dfb7c9562dfa35f36345348ad2f2d5dfa",
            "sourceType": "curated",
            "displayName": "S. cerevisiae transcriptomes",
            "lastModified": "2026-05-27T20:00:00-04:00",
        }
    )
    assert overview.short_display_name is None
    assert overview.description is None
    assert overview.dataset_id == "DS_ccab256dfb"


def test_study_overview_keeps_the_lowercase_sha1hash_key() -> None:
    """/studies spells it sha1hash; /permissions spells it sha1Hash."""
    overview = EdaStudyOverview.model_validate(
        {
            "id": "STUDY_x",
            "datasetId": "DS_x",
            "sha1hash": "abc",
            "sourceType": "curated",
            "displayName": "x",
            "lastModified": "2026-05-27T20:00:00-04:00",
        }
    )
    assert overview.sha1hash == "abc"
    assert overview.model_dump(by_alias=True)["sha1hash"] == "abc"


def test_a_user_study_carries_an_empty_sha1hash() -> None:
    parsed = EdaStudiesResponse.model_validate(_load("studies_list.json"))
    user_studies = [s for s in parsed.studies if s.source_type == "user_submitted"]
    assert user_studies
    assert all(s.sha1hash == "" for s in user_studies)
    assert all(s.dataset_id.startswith("EDAUD_") for s in user_studies)


def test_permission_entry_spells_the_hash_with_a_capital_h() -> None:
    parsed = EdaPermissionsResponse.model_validate(_load("permissions.json"))
    entry = parsed.per_dataset["DS_53f554ec6a"]
    assert entry.study_id == "STUDY_53f554ec6a"
    assert entry.sha1_hash
    assert entry.action_authorization.results_all is True


def test_permission_entries_that_omit_declared_required_fields_still_parse() -> None:
    """24 of 880 live entries omit shortDisplayName or description."""
    parsed = EdaPermissionsResponse.model_validate(_load("permissions.json"))
    sparse = [
        e
        for e in parsed.per_dataset.values()
        if e.short_display_name is None or e.description is None
    ]
    assert sparse, "the trimmed fixture must retain the sparse entries"


def test_an_unmodelled_extra_field_is_ignored() -> None:
    overview = EdaStudyOverview.model_validate(
        {
            "id": "STUDY_x",
            "datasetId": "DS_x",
            "sha1hash": "",
            "sourceType": "user_submitted",
            "displayName": "x",
            "lastModified": "2026-05-27T20:00:00-04:00",
            "somethingUpstreamAddedLater": 1,
        }
    )
    assert not hasattr(overview, "somethingUpstreamAddedLater")
