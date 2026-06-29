"""A new leaf step's input-step (AnswerParam) params must be sent as ``""``.

WDK rule (``AnswerParam.java``): an answer param's value is either the empty
string or a step id; for a brand-new step it must be ``""`` (the real input is
wired via the stepTree). ``create_transform_step`` already enforced this;
``create_step`` (leaf path) did not — so a leaf using an input-step search
(e.g. ``GenesByOrthologs``) was rejected. Both now share one helper.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pathfinder.integrations.veupathdb.strategy_api.api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKAnswerParam,
    WDKStringParam,
)


class _StubClient:
    def __init__(self, params: list[object]) -> None:
        self._params = params

    async def get_search_details(self, record_type: str, search_name: str) -> object:
        del record_type, search_name
        return SimpleNamespace(search_data=SimpleNamespace(parameters=self._params))


@pytest.mark.asyncio
async def test_empty_answer_params_forces_input_step_params_empty() -> None:
    api = StrategyAPI(
        _StubClient(
            [  # type: ignore[arg-type]
                WDKAnswerParam(name="gene_result"),
                WDKStringParam(name="MinPercentMinorAlleles"),
            ]
        )
    )

    out = await api._empty_answer_params(
        "transcript",
        "GenesByOrthologs",
        {"organism": '["Toxoplasma gondii ME49"]', "gene_result": "999"},
    )

    assert out["gene_result"] == ""  # forced empty, even over a stale value
    assert out["organism"] == '["Toxoplasma gondii ME49"]'  # non-answer untouched


@pytest.mark.asyncio
async def test_empty_answer_params_noop_without_answer_params() -> None:
    api = StrategyAPI(_StubClient([WDKStringParam(name="x")]))  # type: ignore[arg-type]
    out = await api._empty_answer_params("transcript", "GenesByText", {"x": "kinase"})
    assert out == {"x": "kinase"}
