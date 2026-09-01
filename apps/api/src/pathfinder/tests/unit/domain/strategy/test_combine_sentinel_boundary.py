"""Where the combine sentinel is produced, and what it means to a reader.

The sentinel is a boundary default of the persisted AST. A step's kind comes
from its inputs, so nothing outside this module needs the name to know it is
looking at a combine.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.domain.parameters.values import StringValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.graph_model import (
    StepKind,
    StrategyStep,
    flatten_tree,
    rebuild_tree,
    runs_a_wdk_search,
    wdk_search_name,
)
from pathfinder.domain.strategy.ops import CombineOp

_BOOLEAN_QUESTION = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"


def _combine(**overrides: object) -> StrategyStep:
    base: dict[str, object] = {
        "id": "c",
        "kind": StepKind.COMBINE,
        "primary_input_id": "a",
        "secondary_input_id": "b",
        "operator": CombineOp.INTERSECT,
    }
    return StrategyStep.model_validate(base | overrides)


class TestTheSentinelIsProducedOnlyAtTheBoundary:
    def test_a_two_input_node_with_no_name_is_stamped(self) -> None:
        node = StrategyStepNode(
            primary_input=StrategyStepNode(search_name="a"),
            secondary_input=StrategyStepNode(search_name="b"),
            operator=CombineOp.INTERSECT,
        )

        assert node.search_name == COMBINE_SEARCH_NAME

    def test_a_single_input_node_with_no_name_is_refused(self) -> None:
        """One input is a transform, and a transform names its own search."""
        with pytest.raises(ValidationError, match="searchName"):
            StrategyStepNode(primary_input=StrategyStepNode(search_name="a"))

    def test_a_named_combine_keeps_its_name(self) -> None:
        node = StrategyStepNode(
            search_name=_BOOLEAN_QUESTION,
            primary_input=StrategyStepNode(search_name="a"),
            secondary_input=StrategyStepNode(search_name="b"),
            operator=CombineOp.INTERSECT,
        )

        assert node.search_name == _BOOLEAN_QUESTION

    def test_the_flat_step_of_a_sentinel_combine_has_no_search_name(self) -> None:
        node = StrategyStepNode(
            id="c",
            primary_input=StrategyStepNode(id="a", search_name="a"),
            secondary_input=StrategyStepNode(id="b", search_name="b"),
            operator=CombineOp.INTERSECT,
        )

        assert flatten_tree(node)["c"].search_name is None

    def test_rebuilding_puts_the_sentinel_back(self) -> None:
        steps = {
            "a": StrategyStep(id="a", kind=StepKind.SEARCH, search_name="a"),
            "b": StrategyStep(id="b", kind=StepKind.SEARCH, search_name="b"),
            "c": _combine(),
        }

        assert rebuild_tree("c", steps).search_name == COMBINE_SEARCH_NAME


class TestWhatEachReaderActuallyAsks:
    def test_a_combine_reports_the_sentinel_as_its_outward_name(self) -> None:
        assert wdk_search_name(_combine()) == COMBINE_SEARCH_NAME

    def test_a_combine_wdk_named_reports_that_name(self) -> None:
        assert wdk_search_name(_combine(search_name=_BOOLEAN_QUESTION)) == (
            _BOOLEAN_QUESTION
        )

    def test_a_search_reports_its_own_name(self) -> None:
        step = StrategyStep(
            id="a",
            kind=StepKind.SEARCH,
            search_name="GenesByText",
            parameters={"text_expression": StringValue(value="kinase")},
        )

        assert wdk_search_name(step) == "GenesByText"

    def test_only_a_named_step_runs_a_wdk_search(self) -> None:
        search = StrategyStep(id="a", kind=StepKind.SEARCH, search_name="GenesByText")

        assert runs_a_wdk_search(search)
        assert not runs_a_wdk_search(_combine())
        assert not runs_a_wdk_search(
            StrategyStep(id="b", kind=StepKind.SEARCH, search_name=None)
        )

    def test_a_transform_that_only_carries_the_sentinel_reports_it(self) -> None:
        """A combine that lost a slot round-trips as a transform.

        Its name is still the sentinel, so it still names no runnable search.
        """
        node = StrategyStepNode(
            id="c",
            search_name=COMBINE_SEARCH_NAME,
            primary_input=StrategyStepNode(id="a", search_name="a"),
        )

        step = flatten_tree(node)["c"]

        assert step.kind is StepKind.TRANSFORM
        assert wdk_search_name(step) == COMBINE_SEARCH_NAME
        assert not runs_a_wdk_search(step)
