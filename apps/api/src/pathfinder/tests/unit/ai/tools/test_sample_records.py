from __future__ import annotations

from typing import cast

import pytest

from pathfinder.ai.tools.standalone._result_models import (
    SampleRecordsResult,
    _extract_sample_response,
    _fetch_step_preview,
    _sample_attributes,
)
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKAnswerMeta,
    WDKRecordInstance,
)
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.services.wdk import StrategyAPI

_GENE_ATTRS = ["gene_product", "gene_name", "organism"]


def _answer(records: list[WDKRecordInstance], attributes: list[str]) -> WDKAnswer:
    return WDKAnswer(
        meta=WDKAnswerMeta(
            total_count=len(records),
            record_class_name="transcript",
            attributes=attributes,
        ),
        records=records,
    )


def test_extract_enriches_and_strips_html_from_attribute_values() -> None:
    # WDK returns organism wrapped in <i>...</i>; the tool must surface a clean
    # value alongside the id + product name.
    ans = _answer(
        [
            WDKRecordInstance(
                display_name="PF3D7_0610600",
                attributes={
                    "gene_product": "calcium-dependent protein kinase 2",
                    "gene_name": "CDPK2",
                    "organism": "<i>Plasmodium falciparum 3D7</i>",
                },
            )
        ],
        _GENE_ATTRS,
    )
    result = _extract_sample_response(ans, 123)
    assert isinstance(result, SampleRecordsResult)
    assert result.records[0] == {
        "id": "PF3D7_0610600",
        "gene_product": "calcium-dependent protein kinase 2",
        "gene_name": "CDPK2",
        "organism": "Plasmodium falciparum 3D7",
    }


def test_sample_attributes_requested_for_gene_record_types() -> None:
    assert _sample_attributes("transcript") == _GENE_ATTRS
    assert _sample_attributes("gene") == _GENE_ATTRS
    assert _sample_attributes(None) == _GENE_ATTRS  # app default is transcript


def test_sample_attributes_none_for_non_gene_record_type() -> None:
    assert _sample_attributes("popsetSequence") is None


class _FakeStrategyAPI:
    """``get_step_answer`` succeeds only WITHOUT attributes — simulating a
    record class that rejects the gene attributes."""

    def __init__(self) -> None:
        self.calls: list[list[str] | None] = []

    async def get_step_answer(
        self,
        step_id: int,
        attributes: list[str] | None = None,
        pagination: dict[str, int] | None = None,
        user_id: str | None = None,
    ) -> WDKAnswer:
        self.calls.append(attributes)
        if attributes:
            raise AppError(ErrorCode.WDK_ERROR, "attribute 'gene_product' not found")
        return _answer([WDKRecordInstance(display_name="x1")], [])


@pytest.mark.asyncio
async def test_fetch_falls_back_to_id_only_when_attributes_rejected() -> None:
    api = _FakeStrategyAPI()
    out = await _fetch_step_preview(cast("StrategyAPI", api), 5, 3, _GENE_ATTRS)
    assert isinstance(out, WDKAnswer)  # graceful fallback, not an error
    assert api.calls == [_GENE_ATTRS, None]  # tried enriched, then id-only
