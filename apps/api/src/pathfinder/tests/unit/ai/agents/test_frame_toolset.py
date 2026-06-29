from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone.frame_spec import drop_criterion, set_structure
from pathfinder.ai.tools.toolsets.frame import (
    _frame_enum_overrides,
    build_toolset,
)
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp


def _ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.deps.agent_state = state
    return ctx


def _leaf_structure(criterion_id: str) -> SpecStructure:
    return SpecStructure(root=StructureNode(kind="leaf", criterion_id=criterion_id))


def test_frame_toolset_exposes_get_parameter_options() -> None:
    # FRAME must be able to inspect a param's vocabulary (e.g. a tree-box
    # organism list) to find valid values or learn a target is unavailable.
    tools = build_toolset().wrapped.tools  # type: ignore[attr-defined]
    assert "get_parameter_options" in tools


def test_frame_enum_overrides_guards_get_parameter_options_search_name() -> None:
    ctx = MagicMock()
    ctx.deps.agent_state.candidate_search_names.return_value = ["GenesByOrthologs"]
    ctx.deps.agent_state.discovered_search_names.return_value = []
    overrides = _frame_enum_overrides(ctx)
    assert "GenesByOrthologs" in overrides[("get_parameter_options", "search_name")]


def test_frame_set_criterion_replaces_by_id() -> None:
    st = AgentToolState()
    st.frame_set_criterion(Criterion(id="c1", text="a", search_name="S1"))
    st.frame_set_criterion(Criterion(id="c1", text="a2", search_name="S2"))
    assert len(st.operational_spec_draft.criteria) == 1
    assert st.operational_spec_draft.criteria[0].search_name == "S2"


@pytest.mark.asyncio
async def test_set_structure_transform_operator_builds_transform_node() -> None:
    # A search that maps a prior result (e.g. GenesByOrthologs) is wired with the
    # TRANSFORM operator: it transforms the accumulated subtree rather than being
    # boolean-combined as a standalone leaf.
    st = AgentToolState()
    await set_structure(
        _ctx(st),
        criterion_ids=["c_seed", "c_ortho", "c_pf"],
        operators=["TRANSFORM", "INTERSECT"],
    )
    root = st.operational_spec_draft.structure.root  # type: ignore[union-attr]
    assert root.kind == "combine"
    assert root.operator == CombineOp.INTERSECT
    assert root.inputs[1].criterion_id == "c_pf"
    transform = root.inputs[0]
    assert transform.kind == "transform"
    assert transform.criterion_id == "c_ortho"
    assert transform.inputs[0].criterion_id == "c_seed"


@pytest.mark.asyncio
async def test_set_structure_builds_left_fold_with_per_step_operators() -> None:
    st = AgentToolState()
    await set_structure(
        _ctx(st), criterion_ids=["c1", "c2", "c3"], operators=["INTERSECT", "UNION"]
    )
    root = st.operational_spec_draft.structure.root  # type: ignore[union-attr]
    assert root.kind == "combine"
    assert root.operator == CombineOp.UNION  # outermost fold step
    assert root.inputs[1].criterion_id == "c3"
    assert root.inputs[0].operator == CombineOp.INTERSECT  # inner fold


def test_drop_criterion_removes_from_criteria_and_records() -> None:
    st = AgentToolState()
    st.frame_set_criterion(
        Criterion(id="c_x", text="disorder fraction", search_name="S1")
    )
    st.frame_set_criterion(Criterion(id="c_keep", text="keep me", search_name="S2"))

    drop_criterion(_ctx(st), criterion_id="c_x", reason="search down")

    assert [c.id for c in st.operational_spec_draft.criteria] == ["c_keep"]
    dropped = st.operational_spec_draft.dropped[0]
    assert dropped.text == "disorder fraction"
    assert dropped.reason == "search down"


def test_drop_criterion_unblocks_ready_to_build() -> None:
    # The real bug: a dropped-but-not-removed criterion with an open param keeps
    # ready_to_build False forever, so the agent can't recover from a down search.
    st = AgentToolState()
    st.frame_set_criterion(Criterion(id="ok", text="bound", search_name="S1"))
    st.frame_set_criterion(
        Criterion(
            id="broken",
            text="broken",
            search_name="GenesByOrthologPattern",
            open_params=[OpenSlot(param_name="organism", question="pick")],
        )
    )
    st.operational_spec_draft.structure = _leaf_structure("ok")
    assert st.operational_spec_draft.ready_to_build is False

    drop_criterion(_ctx(st), criterion_id="broken", reason="search down")

    assert st.operational_spec_draft.ready_to_build is True


def test_drop_criterion_unknown_id_raises_model_retry() -> None:
    st = AgentToolState()
    st.frame_set_criterion(Criterion(id="c1", text="a", search_name="S1"))
    with pytest.raises(ModelRetry):
        drop_criterion(_ctx(st), criterion_id="nope", reason="x")
