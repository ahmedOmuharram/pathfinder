"""Branch terms become leaves before a step is created.

Under ``countOnlyLeaves`` WDK counts selected leaves, so a branch term reaches
it as a selection of nothing.
"""

from __future__ import annotations

import json
from typing import cast

from assistant_core.platform.types import JSONObject
from pydantic import JsonValue

from pathfinder.domain.parameters.wdk_vocab import FAKE_ALL_SENTINEL
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.strategy_api.api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam, WDKParameter

_LEAVES = ["17 Hour", "18 Hour", "19 Hour"]
_OTHER_LEAVES = ["24 Hour", "25 Hour"]


def _tree() -> JSONObject:
    return cast(
        "JSONObject",
        {
            "data": {"term": "@@fake@@", "display": "@@fake@@"},
            "children": [
                {
                    "data": {"term": "Trophozoite", "display": "17-30 Hours"},
                    "children": [
                        {
                            "data": {"term": "Early Trophozoite", "display": "17-23"},
                            "children": [
                                {"data": {"term": t, "display": t}} for t in _LEAVES
                            ],
                        },
                        {
                            "data": {"term": "Late Trophozoite", "display": "24-30"},
                            "children": [
                                {"data": {"term": t, "display": t}}
                                for t in _OTHER_LEAVES
                            ],
                        },
                    ],
                }
            ],
        },
    )


def _param(*, count_only_leaves: bool = True) -> WDKParameter:
    raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": "samples",
        "display_name": "Samples",
        "display_type": "treeBox",
        "count_only_leaves": count_only_leaves,
        "vocabulary": cast("JsonValue", _tree()),
        "allow_empty_value": False,
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


def _expand(value: list[str], *, count_only_leaves: bool = True) -> list[str]:
    api = StrategyAPI(VEuPathDBClient("https://example.invalid/service"), "1")
    result = api._expand_specs(
        [_param(count_only_leaves=count_only_leaves)],
        {"samples": json.dumps(value)},
        "GenesByProfile",
    )
    return list(json.loads(result["samples"]))


class TestABranchBecomesItsLeaves:
    def test_a_top_branch_expands_to_every_leaf_under_it(self) -> None:
        assert _expand(["Trophozoite"]) == [*_LEAVES, *_OTHER_LEAVES]

    def test_an_inner_branch_expands_to_its_own_leaves(self) -> None:
        assert _expand(["Early Trophozoite"]) == _LEAVES

    def test_two_branches_do_not_repeat_a_leaf(self) -> None:
        expanded = _expand(["Trophozoite", "Early Trophozoite"])

        assert expanded == [*_LEAVES, *_OTHER_LEAVES]

    def test_a_leaf_is_left_alone(self) -> None:
        assert _expand(["18 Hour"]) == ["18 Hour"]

    def test_a_branch_and_a_leaf_merge(self) -> None:
        assert _expand(["Late Trophozoite", "18 Hour"]) == [*_OTHER_LEAVES, "18 Hour"]


class TestWhatIsLeftUntouched:
    def test_a_param_that_counts_branches_is_not_expanded(self) -> None:
        assert _expand(["Trophozoite"], count_only_leaves=False) == ["Trophozoite"]

    def test_an_unknown_term_is_passed_through_for_wdk_to_judge(self) -> None:
        assert _expand(["99 Hour"]) == ["99 Hour"]

    def test_the_synthetic_root_does_not_select_the_whole_vocabulary(self) -> None:
        # It names no real term, so expanding it would turn a filter into a
        # criterion that removes nothing.
        assert _expand([FAKE_ALL_SENTINEL]) != [*_LEAVES, *_OTHER_LEAVES]

    def test_the_synthetic_root_is_left_for_wdk_to_refuse(self) -> None:
        assert _expand([FAKE_ALL_SENTINEL]) == [FAKE_ALL_SENTINEL]
