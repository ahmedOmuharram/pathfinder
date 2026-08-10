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
async def test_set_structure_wires_a_transform_to_its_input() -> None:
    # A search that maps a prior result (e.g. GenesByOrthologs) is a transform
    # node holding that subtree as its input, never a standalone leaf.
    st = AgentToolState()
    await set_structure(
        _ctx(st),
        root=StructureNode(
            kind="combine",
            operator=CombineOp.INTERSECT,
            inputs=[
                StructureNode(
                    kind="transform",
                    criterion_id="c_ortho",
                    inputs=[StructureNode(kind="leaf", criterion_id="c_seed")],
                ),
                StructureNode(kind="leaf", criterion_id="c_pf"),
            ],
        ),
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
async def test_set_structure_keeps_each_nodes_own_operator() -> None:
    st = AgentToolState()
    await set_structure(
        _ctx(st),
        root=StructureNode(
            kind="combine",
            operator=CombineOp.UNION,
            inputs=[
                StructureNode(
                    kind="combine",
                    operator=CombineOp.INTERSECT,
                    inputs=[
                        StructureNode(kind="leaf", criterion_id="c1"),
                        StructureNode(kind="leaf", criterion_id="c2"),
                    ],
                ),
                StructureNode(kind="leaf", criterion_id="c3"),
            ],
        ),
    )
    root = st.operational_spec_draft.structure.root  # type: ignore[union-attr]
    assert root.operator == CombineOp.UNION
    assert root.inputs[1].criterion_id == "c3"
    assert root.inputs[0].operator == CombineOp.INTERSECT


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


class TestNestedBranches:
    """A left fold cannot express a UNION branch on the secondary input.

    FRAME's own instruction says "when a property has several evidence
    sources, UNION them into one branch first, then INTERSECT that branch
    with the others" -- which the flat criterion_ids/operators signature
    could not encode. The real drug-target strategy needs

        (A UNION B UNION C UNION D) -> TRANSFORM
          INTERSECT (E UNION F)
          INTERSECT G

    and a left fold turns the (E UNION F) branch into
    ``((... INTERSECT E) UNION F)``, which is a different question.
    WDK step trees carry primary AND secondary inputs, so this shape is
    representable end to end; only the tool was flattening it.
    """

    @pytest.mark.asyncio
    async def test_a_union_branch_survives_on_the_secondary_input(self) -> None:
        st = AgentToolState()

        await set_structure(
            _ctx(st),
            root=StructureNode(
                kind="combine",
                operator=CombineOp.INTERSECT,
                inputs=[
                    StructureNode(kind="leaf", criterion_id="kinases"),
                    StructureNode(
                        kind="combine",
                        operator=CombineOp.UNION,
                        inputs=[
                            StructureNode(kind="leaf", criterion_id="massspec"),
                            StructureNode(kind="leaf", criterion_id="derisi"),
                        ],
                    ),
                ],
            ),
        )

        root = st.operational_spec_draft.structure.root  # type: ignore[union-attr]
        assert root.operator == CombineOp.INTERSECT
        branch = root.inputs[1]
        assert branch.kind == "combine"
        assert branch.operator == CombineOp.UNION
        assert [n.criterion_id for n in branch.inputs] == ["massspec", "derisi"]

    @pytest.mark.asyncio
    async def test_a_transform_can_sit_above_a_union_branch(self) -> None:
        st = AgentToolState()

        await set_structure(
            _ctx(st),
            root=StructureNode(
                kind="transform",
                criterion_id="orthologs",
                inputs=[
                    StructureNode(
                        kind="combine",
                        operator=CombineOp.UNION,
                        inputs=[
                            StructureNode(kind="leaf", criterion_id="ec"),
                            StructureNode(kind="leaf", criterion_id="interpro"),
                        ],
                    )
                ],
            ),
        )

        root = st.operational_spec_draft.structure.root  # type: ignore[union-attr]
        assert root.kind == "transform"
        assert root.criterion_id == "orthologs"
        assert root.inputs[0].operator == CombineOp.UNION

    @pytest.mark.asyncio
    async def test_a_single_leaf_is_still_valid(self) -> None:
        st = AgentToolState()

        result = await set_structure(
            _ctx(st), root=StructureNode(kind="leaf", criterion_id="only")
        )

        root = st.operational_spec_draft.structure.root  # type: ignore[union-attr]
        assert root.kind == "leaf"
        assert root.criterion_id == "only"
        assert result.criteria_combined == 1

    @pytest.mark.asyncio
    async def test_it_counts_every_criterion_in_the_tree(self) -> None:
        st = AgentToolState()

        result = await set_structure(
            _ctx(st),
            root=StructureNode(
                kind="combine",
                operator=CombineOp.INTERSECT,
                inputs=[
                    StructureNode(kind="leaf", criterion_id="a"),
                    StructureNode(
                        kind="combine",
                        operator=CombineOp.UNION,
                        inputs=[
                            StructureNode(kind="leaf", criterion_id="b"),
                            StructureNode(kind="leaf", criterion_id="c"),
                        ],
                    ),
                ],
            ),
        )

        assert result.criteria_combined == 3


def _resolved_no_slots() -> ResolvedParams:
    return ResolvedParams(params={}, open_slots=[])


async def _noop_validate(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {}



class TestMultiValueOverrides:
    """A multi-pick slot must be answerable with a list.

    ``param_overrides`` was ``dict[str, str]``, so answering a multi-pick
    open slot with the natural ``["20 Hour", "21 Hour", ...]`` raised a
    Pydantic ``string_type`` error before any WDK call. Observed live: the
    model retried, then told the user "the API rejected the combined sample
    encoding" and offered to build 13 separate search arms -- for a payload
    WDK accepts (13 DeRisi time points, totalCount 841).

    The tool surface, not WDK, could not express the value.

    The first fix also encoded the list to WDK wire form here. That was wrong:
    the resolver then matched the whole serialized array against the vocabulary
    as ONE option, found nothing, and validation reported the model's own
    correct answer as invalid. The list stays a list; the codec encodes it at
    the wire, which is the only place that wants a string.
    """

    @pytest.mark.asyncio
    async def test_a_list_override_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        async def fake_resolve(**kwargs: object) -> ResolvedParams:
            captured.update(kwargs)
            return _resolved_no_slots()

        monkeypatch.setattr(frame_spec, "resolve_search_params", fake_resolve)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)

        st = AgentToolState()
        await frame_spec.set_criterion(
            _ctx(st),
            criterion_id="derisi",
            text="top 10% expression 20-32h",
            search_name="GenesByMicroarray",
            param_overrides={"samples_percentile_generic": ["20 Hour", "21 Hour"]},
        )

        overrides = captured["overrides"]
        assert isinstance(overrides, dict)
        assert overrides["samples_percentile_generic"] == ["20 Hour", "21 Hour"]

    @pytest.mark.asyncio
    async def test_a_plain_string_override_is_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_resolve(**kwargs: object) -> ResolvedParams:
            captured.update(kwargs)
            return _resolved_no_slots()

        monkeypatch.setattr(frame_spec, "resolve_search_params", fake_resolve)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)

        st = AgentToolState()
        await frame_spec.set_criterion(
            _ctx(st),
            criterion_id="c",
            text="t",
            search_name="S",
            param_overrides={"organism": "Plasmodium falciparum 3D7"},
        )

        overrides = captured["overrides"]
        assert isinstance(overrides, dict)
        assert overrides["organism"] == "Plasmodium falciparum 3D7"
