from __future__ import annotations

import json
from pathlib import Path

from pathfinder.integrations.eda.models import (
    TABULAR_JSON,
    EdaAppsResponse,
    EdaComputeJob,
    EdaCountResponse,
    EdaDistributionResponse,
    VolcanoStatsResponse,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_the_job_id_key_is_capital_i_capital_d() -> None:
    job = EdaComputeJob.model_validate(_load("compute_job_lookup.json"))
    assert len(job.job_id) == 32
    assert job.status in {
        "queued",
        "in-progress",
        "complete",
        "failed",
        "expired",
        "no-such-job",
    }


def test_queue_position_is_absent_when_a_job_starts_at_once() -> None:
    job = EdaComputeJob.model_validate({"jobID": "a" * 32, "status": "queued"})
    assert job.queue_position is None


def test_volcano_numbers_arrive_as_strings() -> None:
    parsed = VolcanoStatsResponse.model_validate(_load("volcano_statistics.json"))
    first = parsed.statistics[0]
    assert isinstance(first.effect_size, str)
    assert isinstance(first.p_value, str)
    assert parsed.effect_size_label == "log2(Fold Change)"
    assert parsed.p_value_floor == "1e-200"
    assert parsed.adjusted_p_value_floor is None


def test_a_volcano_row_may_omit_both_p_values() -> None:
    parsed = VolcanoStatsResponse.model_validate(
        {
            "effectSizeLabel": "log2(Fold Change)",
            "statistics": [
                {"effectSize": "-1.49447459261845", "pointID": "PF3D7_MIT04200"}
            ],
        }
    )
    row = parsed.statistics[0]
    assert row.point_id == "PF3D7_MIT04200"
    assert row.p_value is None
    assert row.adjusted_p_value is None


def test_the_point_id_key_is_capital_i_capital_d_on_the_wire() -> None:
    parsed = VolcanoStatsResponse.model_validate(
        {"statistics": [{"effectSize": "1.0", "pointID": "PF3D7_0100200"}]}
    )
    assert parsed.statistics[0].point_id == "PF3D7_0100200"


def test_count_response_carries_only_a_count() -> None:
    parsed = EdaCountResponse.model_validate(_load("count_unfiltered.json"))
    assert parsed.count == 4279


def test_a_categorical_distribution_has_no_subset_min_or_mean() -> None:
    parsed = EdaDistributionResponse.model_validate(
        _load("distribution_categorical.json")
    )
    assert parsed.statistics.subset_min is None
    assert parsed.statistics.subset_mean is None
    assert parsed.statistics.subset_size == 4279
    assert parsed.statistics.num_var_values == 8409
    labels = {bin_.bin_label for bin_ in parsed.histogram}
    assert "P. berghei" in labels


def test_bin_bounds_are_strings_even_for_a_numeric_variable() -> None:
    parsed = EdaDistributionResponse.model_validate(
        {
            "histogram": [
                {
                    "value": 13,
                    "binStart": "0.0",
                    "binEnd": "5.0",
                    "binLabel": "[0.0,5.0)",
                }
            ],
            "statistics": {
                "subsetSize": 48721,
                "subsetMin": 3.0,
                "subsetMax": 18.9,
                "subsetMean": 12.032154770825814,
                "numVarValues": 36570,
                "numDistinctValues": 174,
                "numDistinctEntityRecords": 36570,
                "numMissingCases": 12151,
            },
        }
    )
    assert parsed.histogram[0].bin_start == "0.0"
    assert parsed.statistics.subset_mean is not None


def test_the_tabular_json_body_is_a_bare_array_of_arrays() -> None:
    rows = TABULAR_JSON.validate_python(_load("tabular_json.json"))
    assert rows[0][0].endswith("_stable_id")
    assert len(rows) > 1


def test_apps_declare_their_visualizations_and_their_projects() -> None:
    parsed = EdaAppsResponse.model_validate(_load("apps.json"))
    by_name = {app.name: app for app in parsed.apps}
    de = by_name["differentialexpression"]
    assert de.compute_name == "differentialexpression"
    assert [v.name for v in de.visualizations] == ["volcanoplot"]
    assert "PlasmoDB" in de.projects
    assert by_name["distributions"].compute_name is None
