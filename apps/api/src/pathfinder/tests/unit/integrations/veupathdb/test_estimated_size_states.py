"""A negative estimated size is the absence of a count, not a count."""

from __future__ import annotations

import pytest

from pathfinder.integrations.veupathdb.wdk_models import WDKStep

_SPEC = {
    "id": 1,
    "searchName": "GenesByX",
    "searchConfig": {"parameters": {}},
}


def _step(**extra: object) -> WDKStep:
    return WDKStep.model_validate({**_SPEC, **extra})


class TestANegativeSizeIsNotACount:
    def test_minus_one_reads_as_no_count(self) -> None:
        assert _step(estimatedSize=-1).estimated_size is None

    def test_any_negative_reads_as_no_count(self) -> None:
        assert _step(estimatedSize=-42).estimated_size is None


class TestARealCountSurvives:
    def test_zero_is_a_real_result(self) -> None:
        # A search that matched nothing is a scientific finding, not a gap.
        assert _step(estimatedSize=0).estimated_size == 0

    def test_a_positive_count_is_kept(self) -> None:
        assert _step(estimatedSize=3392).estimated_size == 3392


class TestAbsence:
    def test_an_omitted_key_reads_as_no_count(self) -> None:
        assert _step().estimated_size is None


@pytest.mark.parametrize("size", [-1, -2, -1000])
def test_no_negative_ever_reaches_a_caller(size: int) -> None:
    value = _step(estimatedSize=size).estimated_size
    assert value is None or value >= 0
