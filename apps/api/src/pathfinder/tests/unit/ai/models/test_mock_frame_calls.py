"""The mock FRAME flow emits calls the real tools accept.

The mock drives the production ``set_criterion`` and ``set_structure``, so a
canned argument shape that has drifted from the tool signature fails only in an
e2e run, and reads there as a pipeline fault.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter
from pydantic_ai.messages import ToolCallPart

from pathfinder.ai.models.mock_specs import (
    COMBINED_SPEC,
    SINGLE_SPEC,
    SpecPlan,
    frame_call,
    set_criterion_args,
    set_structure_args,
)
from pathfinder.ai.tools.standalone.frame_spec import ParamProposals
from pathfinder.domain.strategy.operational_spec import StructureNode
from pathfinder.domain.strategy.ops import CombineOp

_SPECS = [SINGLE_SPEC, COMBINED_SPEC]


@pytest.mark.parametrize("spec", _SPECS)
def test_every_criterion_proposes_its_params(spec: SpecPlan) -> None:
    adapter: TypeAdapter[ParamProposals] = TypeAdapter(ParamProposals)

    for criterion in spec.criteria:
        args = set_criterion_args(criterion, with_params=True)
        assert adapter.validate_python(args["params"])
        assert "organism" in args["params"], "GenesByTaxon's only visible param"


@pytest.mark.parametrize("spec", _SPECS)
def test_the_sheet_is_read_before_the_params_are_proposed(spec: SpecPlan) -> None:
    # The sheet call carries no `params`, so the tool answers with the sheet
    # instead of binding the criterion.
    for criterion in spec.criteria:
        assert "params" not in set_criterion_args(criterion, with_params=False)


def test_frame_drives_sheet_then_proposal_for_each_criterion() -> None:
    calls: list[ToolCallPart] = []
    for _ in range(2 * len(COMBINED_SPEC.criteria)):
        calls.append(frame_call(COMBINED_SPEC, calls))

    assert [
        (c.args_as_dict()["criterion_id"], "params" in c.args_as_dict()) for c in calls
    ] == [
        ("c1", False),
        ("c1", True),
        ("c2", False),
        ("c2", True),
    ]
    assert frame_call(COMBINED_SPEC, calls).tool_name == "set_structure"


@pytest.mark.parametrize("spec", _SPECS)
def test_the_structure_call_is_a_tree(spec: SpecPlan) -> None:
    root = StructureNode.model_validate(set_structure_args(spec)["root"])

    named = _criterion_ids(root)
    assert named == [c.criterion_id for c in spec.criteria]


def test_two_criteria_fold_under_the_plans_operator() -> None:
    root = StructureNode.model_validate(set_structure_args(COMBINED_SPEC)["root"])

    assert root.kind == "combine"
    assert root.operator == CombineOp.UNION


def _criterion_ids(node: StructureNode) -> list[str]:
    own = [node.criterion_id] if node.criterion_id else []
    return own + [cid for child in node.inputs for cid in _criterion_ids(child)]
