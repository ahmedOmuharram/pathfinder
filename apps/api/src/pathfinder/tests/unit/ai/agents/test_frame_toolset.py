from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import frame_spec
from pathfinder.ai.tools.standalone.frame_spec import (
    SetCriterionResult,
    drop_criterion,
    set_criterion,
    set_structure,
)
from pathfinder.ai.tools.toolsets.frame import (
    _frame_enum_overrides,
    build_toolset,
)
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog.param_dag import ResolvedParams


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
    # No search has been abandoned this turn; a bare MagicMock here would stand
    # in for the outage set and silently swallow every candidate.
    ctx.deps.service_outage.unavailable_searches.return_value = frozenset()
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


def _frame_ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.deps.agent_state = state
    ctx.deps.site_id = "plasmodb"
    ctx.deps.strategy_session.get_graph.return_value = None  # -> "transcript"
    return ctx


@pytest.mark.asyncio
async def test_set_criterion_retries_on_invalid_resolved_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A complete (no open slots) binding whose resolved values WDK rejects must
    # surface a did-you-mean retry at FRAME — not slip through to fail the build.
    st = AgentToolState()

    async def _resolve(**_kw: object) -> ResolvedParams:
        return ResolvedParams(
            params={"text_fields": MultiPickValue(values=["product,Notes"])},
            open_slots=[],
            unresolved_required=[],
        )

    async def _validate(_ctx: object, **_kw: object) -> dict[str, object]:
        raise ValidationError(
            title="Invalid parameter value: Parameter 'text_fields' does not "
            "accept 'product,Notes'."
        )

    monkeypatch.setattr(frame_spec, "resolve_search_params", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)

    with pytest.raises(ModelRetry) as exc:
        await set_criterion(
            _frame_ctx(st),
            criterion_id="c1",
            text="annotated male gametocyte",
            search_name="GenesByText",
            param_overrides={"text_fields": "product,Notes"},
        )
    assert "text_fields" in str(exc.value)
    assert st.operational_spec_draft.criteria == []  # not bound with the bad value


@pytest.mark.asyncio
async def test_set_criterion_skips_validation_when_open_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Open slots = a required param still unresolved; validating now would falsely
    # trip "missing required", so the gate must NOT run until the spec is complete.
    st = AgentToolState()
    validated = False

    async def _resolve(**_kw: object) -> ResolvedParams:
        return ResolvedParams(
            params={"organism": MultiPickValue(values=["Pf3D7"])},
            open_slots=[OpenSlot(param_name="samples", question="pick")],
            unresolved_required=["samples"],
        )

    async def _validate(_ctx: object, **_kw: object) -> dict[str, object]:
        nonlocal validated
        validated = True
        return {}

    monkeypatch.setattr(frame_spec, "resolve_search_params", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)

    result = await set_criterion(
        _frame_ctx(st), criterion_id="c1", text="x", search_name="GenesByRNASeq"
    )
    assert validated is False
    assert any(s.param_name == "samples" for s in result.open_slots)
    assert st.operational_spec_draft.criteria[0].id == "c1"


@pytest.mark.asyncio
async def test_set_criterion_binds_when_resolved_params_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    st = AgentToolState()

    async def _resolve(**_kw: object) -> ResolvedParams:
        return ResolvedParams(
            params={"organism": MultiPickValue(values=["Pf3D7"])},
            open_slots=[],
            unresolved_required=[],
        )

    async def _validate(_ctx: object, **_kw: object) -> dict[str, object]:
        return {"organism": MultiPickValue(values=["Pf3D7"])}

    monkeypatch.setattr(frame_spec, "resolve_search_params", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)

    result = await set_criterion(
        _frame_ctx(st),
        criterion_id="c1",
        text="x",
        search_name="GenesWithSignalPeptide",
    )
    assert isinstance(result, SetCriterionResult)
    assert result.criterion_id == "c1"
    assert result.search_name == "GenesWithSignalPeptide"
    # Report the bound VALUE, not just the name: a silently wrong binding (the
    # GenesByText run bound `text_expression` to WDK's `*reductase` example and
    # still reported "resolved") is invisible when only names come back.
    assert result.resolved_params == {"organism": '["Pf3D7"]'}
    assert result.open_slots == []
    assert st.operational_spec_draft.criteria[0].id == "c1"
