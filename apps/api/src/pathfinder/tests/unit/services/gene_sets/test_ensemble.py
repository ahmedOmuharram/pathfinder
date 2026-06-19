from __future__ import annotations

import pytest

from pathfinder.services.gene_sets.ensemble import compute_ensemble_scores


def test_frequency_count_and_positive_flag() -> None:
    scores = compute_ensemble_scores(
        [["g1", "g2"], ["g1", "g3"], ["g1", "g2"]],
        positive_controls=["g2"],
    )
    assert [s["geneId"] for s in scores] == ["g1", "g2", "g3"]

    g1, g2, g3 = scores
    assert g1 == {
        "geneId": "g1",
        "frequency": 1.0,
        "count": 3,
        "total": 3,
        "inPositives": False,
    }
    assert g2["count"] == 2
    assert g2["frequency"] == pytest.approx(2.0 / 3.0)
    assert g2["inPositives"] is True
    assert g3["count"] == 1
    assert g3["frequency"] == pytest.approx(1.0 / 3.0)
    assert g3["inPositives"] is False


def test_ties_break_by_gene_id_ascending() -> None:
    scores = compute_ensemble_scores([["zebra", "apple"]])
    assert [s["geneId"] for s in scores] == ["apple", "zebra"]
    assert all(s["frequency"] == 1.0 and s["total"] == 1 for s in scores)


def test_empty_input_returns_empty() -> None:
    assert compute_ensemble_scores([]) == []
