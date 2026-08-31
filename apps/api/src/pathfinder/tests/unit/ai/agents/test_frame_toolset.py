from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic_ai import ModelRetry
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.tools.standalone import frame_spec
from pathfinder.ai.tools.standalone._frame_proposals import (
    ParamProposals,
    coerce_proposals,
)
from pathfinder.ai.tools.standalone.frame_spec import (
    SetCriterionResult,
    drop_criterion,
    set_criterion,
)
from pathfinder.ai.tools.standalone.frame_structure import set_structure
from pathfinder.ai.tools.toolsets.frame import (
    _frame_enum_overrides,
    build_toolset,
)
from pathfinder.domain.parameters.value_codec import to_wire
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption, WDKVocabTerm
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.services.catalog import searches
from pathfinder.services.catalog.param_dag import (
    ParamFetcher,
    ResolvedParams,
    UnknownParameterError,
)
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_param_info_typed,
)
from pathfinder.services.catalog.param_validation import ValidatedParams

ParamsAt = Callable[[dict[str, str]], list[ParameterInfo]]


def _serve(monkeypatch: pytest.MonkeyPatch, at: ParamsAt) -> None:
    """Serve one search's parameters from a context-to-parameters function."""

    def _fetch_at(*_args: object) -> ParamFetcher:
        async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
            return at(context)

        return fetch_at

    monkeypatch.setattr(frame_spec, "wdk_fetch_at", _fetch_at)


def _serve_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, lambda _context: [])


def _refuse_param_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if the sheet reads the search a second time.

    The sheet and the registry entry come from one WDK read; a param fetch
    beside it is the duplicate GET this replaced.
    """

    def _explode(_context: dict[str, str]) -> list[ParameterInfo]:
        message = "the sheet must not fetch the params separately"
        raise AssertionError(message)

    _serve(monkeypatch, _explode)


def _ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps.agent_state = state
    return ctx


def _leaf_structure(criterion_id: str) -> SpecStructure:
    return SpecStructure(root=StructureNode(kind="leaf", criterion_id=criterion_id))


def _drafted_root(state: AgentToolState) -> StructureNode:
    """The root of the structure the draft holds, which each caller has just set."""
    structure = state.operational_spec_draft.structure
    assert structure is not None
    return structure.root


def _frame_tool_names() -> set[str]:
    """The tool names FRAME registers, read through the enum-guard wrapper."""
    toolset = build_toolset()
    assert isinstance(toolset, WrapperToolset)
    registered = toolset.wrapped
    assert isinstance(registered, FunctionToolset)
    return set(registered.tools)


def test_frame_toolset_exposes_get_parameter_options() -> None:
    # FRAME must be able to inspect a param's vocabulary (e.g. a tree-box
    # organism list) to find valid values or learn a target is unavailable.
    assert "get_parameter_options" in _frame_tool_names()


def test_frame_toolset_exposes_lookup_phyletic_codes() -> None:
    # The FRAME instructions and the phyletic retry both send the model to this
    # tool, so a species name it cannot spell has somewhere to go.
    assert "lookup_phyletic_codes" in _frame_tool_names()


def test_frame_enum_overrides_guards_get_parameter_options_search_name() -> None:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
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
    root = _drafted_root(st)
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
    root = _drafted_root(st)
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
    ctx.tool_call_id = "call_1"
    ctx.deps.agent_state = state
    ctx.deps.site_id = "plasmodb"
    graph = MagicMock()
    graph.record_type = "transcript"
    # A strategy's own record type answers first, so nothing reads the catalog.
    ctx.deps.strategy_session.get_graph.return_value = graph
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

    async def _validate(_ctx: object, **_kw: object) -> ValidatedParams:
        raise ValidationError(
            title="Invalid parameter value: Parameter 'text_fields' does not "
            "accept 'product,Notes'."
        )

    monkeypatch.setattr(frame_spec, "resolve_params_with_intent", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)
    _serve(monkeypatch, lambda _context: [_pi("text_fields", "multi-pick-vocabulary")])
    _serve_bare_definition(monkeypatch)

    with pytest.raises(ModelRetry) as exc:
        await set_criterion(
            _frame_ctx(st),
            criterion_id="c1",
            text="annotated male gametocyte",
            search_name="GenesByText",
            params={"text_fields": "product,Notes"},
        )
    assert "does not accept" in str(exc.value), "the WDK rejection, not a name check"
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

    async def _validate(_ctx: object, **_kw: object) -> ValidatedParams:
        nonlocal validated
        validated = True
        return ValidatedParams()

    monkeypatch.setattr(frame_spec, "resolve_params_with_intent", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)
    _serve_nothing(monkeypatch)
    _serve_bare_definition(monkeypatch)

    result = (
        await set_criterion(
            _frame_ctx(st),
            criterion_id="c1",
            text="x",
            search_name="GenesByRNASeq",
            params={},
        )
    ).return_value
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

    async def _validate(_ctx: object, **_kw: object) -> ValidatedParams:
        return ValidatedParams(params={"organism": MultiPickValue(values=["Pf3D7"])})

    monkeypatch.setattr(frame_spec, "resolve_params_with_intent", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)
    _serve_nothing(monkeypatch)
    _serve_bare_definition(monkeypatch)

    result = (
        await set_criterion(
            _frame_ctx(st),
            criterion_id="c1",
            text="x",
            search_name="GenesWithSignalPeptide",
            params={},
        )
    ).return_value
    assert isinstance(result, SetCriterionResult)
    assert result.criterion_id == "c1"
    assert result.search_name == "GenesWithSignalPeptide"
    # Report the bound VALUE, not just the name: a silently wrong binding (the
    # GenesByText run bound `text_expression` to WDK's `*reductase` example and
    # still reported "resolved") is invisible when only names come back.
    assert result.resolved_params == {"organism": '["Pf3D7"]'}
    assert result.open_slots == []
    # A proposal already carries the names, so the template would only repeat them.
    assert result.params_template == {}
    assert st.operational_spec_draft.criteria[0].id == "c1"


async def _sheet_call(
    state: AgentToolState, criterion_id: str = "c1"
) -> SetCriterionResult:
    return (
        await set_criterion(
            _frame_ctx(state),
            criterion_id=criterion_id,
            text="kinases",
            search_name="GenesByText",
        )
    ).return_value


class TestTheSheetComesBackFromSetCriterion:
    """A call with no ``params`` answers with the sheet and records nothing.

    The sheet has to be the tool result immediately before the proposal;
    reading it many calls earlier is what let invented parameter names through.
    The sheet and the registry entry come from ONE read of the search, so they
    can never disagree about which parameters exist.
    """

    @pytest.mark.asyncio
    async def test_no_params_returns_one_entry_per_visible_param(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reads = _serve_search_details(monkeypatch)
        _refuse_param_fetch(monkeypatch)
        st = AgentToolState()

        result = await _sheet_call(st)

        assert [entry.name for entry in result.decide] == [
            "text_expression",
            "text_search_organism",
            "document_type",
            "text_fields",
        ]
        organism = next(e for e in result.decide if e.name == "text_search_organism")
        assert [o.value for o in organism.vocabulary] == [
            "Plasmodium",
            "Plasmodium falciparum 3D7",
        ]
        assert result.resolved_params == {}
        assert st.operational_spec_draft.criteria == [], "nothing is recorded yet"
        assert reads == ["GenesByText"], "one read serves the sheet and the registry"

    @pytest.mark.asyncio
    async def test_no_params_registers_the_search_from_the_same_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # BUILD's discovery gate reads the registry, so a criterion framed
        # without an overview call must still register its search -- and it must
        # register the same parameters the sheet showed.
        _serve_search_details(monkeypatch)
        st = AgentToolState()

        result = await _sheet_call(st)

        overview = st.get_overview("GenesByText")
        assert overview is not None
        assert overview.record_type == "transcript"
        assert overview.parameter_names == [e.name for e in result.decide]
        assert overview.required_params == ["text_expression", "text_search_organism"]

    @pytest.mark.asyncio
    async def test_the_template_is_the_params_object_to_send_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A template the model copies leaves it no parameter name to invent.
        _serve_search_details(monkeypatch)

        result = await _sheet_call(AgentToolState())

        assert list(result.params_template) == [e.name for e in result.decide]
        assert set(result.params_template.values()) == {None}

    def test_the_template_is_serialized_before_the_sheet(self) -> None:
        # The model reads the result top to bottom; the object it copies has to
        # come before the vocabularies it reads values out of.
        keys = list(SetCriterionResult(criterion_id="c1", search_name="S").model_dump())
        assert keys.index("params_template") < keys.index("decide")

    @pytest.mark.asyncio
    async def test_an_already_registered_search_keeps_its_entry_and_gets_a_sheet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reads = _serve_search_details(monkeypatch)
        st = AgentToolState()
        st.register_search(
            "GenesByText",
            SearchOverview(
                search_name="GenesByText",
                display_name="Read by the overview tool",
                record_type="transcript",
                description="",
                parameter_names=["text_expression"],
                required_params=[],
            ),
        )

        result = await _sheet_call(st)

        assert result.decide, "the sheet still comes back"
        assert reads == ["GenesByText"], "still exactly one read"
        overview = st.get_overview("GenesByText")
        assert overview is not None
        assert overview.display_name == "Read by the overview tool"


class TestASecondSheetDropsTheVocabularies:
    """A repeat sheet for the same criterion costs its vocabularies again.

    The model already holds the vocabulary, so the repeat carries the parameters
    without it and says where to look for an entry it no longer sees.
    """

    @pytest.mark.asyncio
    async def test_the_second_sheet_keeps_the_params_and_drops_the_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_search_details(monkeypatch)
        st = AgentToolState()

        first = await _sheet_call(st)
        second = await _sheet_call(st)

        assert [e.name for e in second.decide] == [e.name for e in first.decide]
        assert all(e.vocabulary == [] for e in second.decide)
        organism = next(e for e in second.decide if e.name == "text_search_organism")
        assert organism.vocabulary_total == 2, "the size is still stated"
        assert organism.required is True
        assert organism.is_tree is False
        assert organism.vocabulary_note == (
            "vocabulary shown in the first sheet; use get_parameter_options("
            "search_name, parameter_id, query=...) for an entry you no longer see"
        )
        text_fields = next(e for e in second.decide if e.name == "text_fields")
        assert text_fields.default == '["product", "Notes"]'
        # The template is the point of the repeat: it costs nothing and it is
        # what the model came back for.
        assert list(second.params_template) == [e.name for e in second.decide]

    @pytest.mark.asyncio
    async def test_another_criterion_on_the_same_search_gets_the_vocabularies(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two criteria over one search are two separate questions, and the
        # second one has never seen the values.
        _serve_search_details(monkeypatch)
        st = AgentToolState()

        await _sheet_call(st, criterion_id="c1")
        other = await _sheet_call(st, criterion_id="c2")

        organism = next(e for e in other.decide if e.name == "text_search_organism")
        assert [o.value for o in organism.vocabulary] == [
            "Plasmodium",
            "Plasmodium falciparum 3D7",
        ]


class TestTheParamsPathRegistersTheSearch:
    """BUILD reads the discovery gate, so every bound criterion needs an entry.

    A proposal can arrive without the sheet call that would have registered the
    search, and the entry is read once and then reused.
    """

    @pytest.mark.asyncio
    async def test_a_params_first_call_registers_the_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)
        reads = _serve_search_details(monkeypatch)
        st = AgentToolState()

        await set_criterion(
            _frame_ctx(st),
            criterion_id="c1",
            text="kinases",
            search_name="GenesByText",
            params={
                "text_expression": "kinase",
                "text_search_organism": ["Plasmodium"],
                "document_type": None,
                "text_fields": None,
            },
        )

        overview = st.get_overview("GenesByText")
        assert overview is not None
        assert overview.record_type == "transcript"
        assert overview.parameter_names == [
            "text_expression",
            "text_search_organism",
            "document_type",
            "text_fields",
        ]
        assert reads == ["GenesByText"]

    @pytest.mark.asyncio
    async def test_a_registered_search_is_not_read_again(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)
        reads = _serve_search_details(monkeypatch)
        st = AgentToolState()

        await _sheet_call(st)
        await set_criterion(
            _frame_ctx(st),
            criterion_id="c1",
            text="kinases",
            search_name="GenesByText",
            params={
                "text_expression": "kinase",
                "text_search_organism": ["Plasmodium"],
                "document_type": None,
                "text_fields": None,
            },
        )

        assert reads == ["GenesByText"], "the sheet's own read serves the registry"


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

        root = _drafted_root(st)
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

        root = _drafted_root(st)
        assert root.kind == "transform"
        assert root.criterion_id == "orthologs"
        assert root.inputs[0].operator == CombineOp.UNION

    @pytest.mark.asyncio
    async def test_a_single_leaf_is_still_valid(self) -> None:
        st = AgentToolState()

        result = (
            await set_structure(
                _ctx(st), root=StructureNode(kind="leaf", criterion_id="only")
            )
        ).return_value

        root = _drafted_root(st)
        assert root.kind == "leaf"
        assert root.criterion_id == "only"
        assert result.criteria_combined == 1

    @pytest.mark.asyncio
    async def test_it_counts_every_criterion_in_the_tree(self) -> None:
        st = AgentToolState()

        result = (
            await set_structure(
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
        ).return_value

        assert result.criteria_combined == 3


def _genes_by_text_wdk() -> list[WDKParameter]:
    """GenesByText as WDK defines it, matching ``_genes_by_text`` param for param.

    The sheet and the registry entry both come from this one definition, so a
    test that lets them disagree is not testing the tool.
    """
    return [
        WDKStringParam(
            name="text_expression", displayName="Text", allowEmptyValue=False
        ),
        WDKEnumParam(
            name="text_search_organism",
            displayName="Organism",
            type="multi-pick-vocabulary",
            allowEmptyValue=False,
            vocabulary=[
                ("Plasmodium", "Plasmodium", None),
                ("Plasmodium falciparum 3D7", "P. falciparum 3D7", None),
            ],
        ),
        WDKStringParam(
            name="document_type",
            displayName="Document type",
            allowEmptyValue=True,
            initialDisplayValue="gene",
        ),
        WDKEnumParam(
            name="text_fields",
            displayName="Fields",
            type="multi-pick-vocabulary",
            allowEmptyValue=True,
            initialDisplayValue='["product", "Notes"]',
            vocabulary=[("product", "product", None), ("Notes", "Notes", None)],
        ),
    ]


def _serve_search_details(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve GenesByText's WDK definition, and record every read of it."""
    reads: list[str] = []

    async def _details(
        record_type: str, name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        reads.append(name)
        return WDKSearchResponse(
            searchData=WDKSearch(
                urlSegment=name,
                displayName="Gene Text Search",
                description="Search gene text.",
                parameters=_genes_by_text_wdk(),
            ),
            validation=StepValidation(level="NONE", is_valid=False),
        )

    client = MagicMock()
    client.get_search_details = _details
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)
    return reads


def _resolved_no_slots() -> ResolvedParams:
    return ResolvedParams(params={}, open_slots=[])


async def _noop_validate(*_args: object, **_kwargs: object) -> ValidatedParams:
    return ValidatedParams()


class TestMultiValueProposals:
    """A multi-pick slot must be answerable with a list.

    ``params`` was ``dict[str, str]``, so answering a multi-pick
    open slot with the natural ``["20 Hour", "21 Hour", ...]`` raised a
    Pydantic ``string_type`` error before any WDK call. Observed: the
    model retried, then told the user "the API rejected the combined sample
    encoding" and offered to build 13 separate search arms -- for a payload
    WDK accepts (13 DeRisi time points, a non-empty result).

    The tool surface, not WDK, could not express the value.

    The first fix also encoded the list to WDK wire form here. That was wrong:
    the resolver then matched the whole serialized array against the vocabulary
    as ONE option, found nothing, and validation reported the model's own
    correct answer as invalid. The list stays a list; the codec encodes it at
    the wire, which is the only place that wants a string.
    """

    @pytest.mark.asyncio
    async def test_a_list_proposal_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_resolve(**kwargs: object) -> ResolvedParams:
            captured.update(kwargs)
            return _resolved_no_slots()

        monkeypatch.setattr(frame_spec, "resolve_params_with_intent", fake_resolve)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
        _serve(
            monkeypatch,
            lambda _context: [
                _pi("samples_percentile_generic", "multi-pick-vocabulary")
            ],
        )
        _serve_bare_definition(monkeypatch)

        st = AgentToolState()
        await frame_spec.set_criterion(
            _frame_ctx(st),
            criterion_id="derisi",
            text="top 10% expression 20-32h",
            search_name="GenesByMicroarray",
            params={"samples_percentile_generic": ["20 Hour", "21 Hour"]},
        )

        overrides = captured["overrides"]
        assert isinstance(overrides, dict)
        assert overrides["samples_percentile_generic"] == ["20 Hour", "21 Hour"]

    @pytest.mark.asyncio
    async def test_a_plain_string_proposal_is_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_resolve(**kwargs: object) -> ResolvedParams:
            captured.update(kwargs)
            return _resolved_no_slots()

        monkeypatch.setattr(frame_spec, "resolve_params_with_intent", fake_resolve)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
        _serve(monkeypatch, lambda _context: [_pi("organism")])
        _serve_bare_definition(monkeypatch)

        st = AgentToolState()
        await frame_spec.set_criterion(
            _frame_ctx(st),
            criterion_id="c",
            text="t",
            search_name="S",
            params={"organism": "Plasmodium falciparum 3D7"},
        )

        overrides = captured["overrides"]
        assert isinstance(overrides, dict)
        assert overrides["organism"] == "Plasmodium falciparum 3D7"

    @pytest.mark.asyncio
    async def test_a_null_proposal_is_not_an_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_resolve(**kwargs: object) -> ResolvedParams:
            captured.update(kwargs)
            return _resolved_no_slots()

        monkeypatch.setattr(frame_spec, "resolve_params_with_intent", fake_resolve)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
        _serve(monkeypatch, lambda _context: [_pi("organism")])
        _serve_bare_definition(monkeypatch)

        st = AgentToolState()
        await frame_spec.set_criterion(
            _frame_ctx(st),
            criterion_id="c",
            text="t",
            search_name="S",
            params={"organism": None},
        )

        overrides = captured["overrides"]
        assert isinstance(overrides, dict)
        assert overrides == {}


class TestProposalCoercion:
    """A proposed value is read as the model types it.

    The tool schema said ``str``, so a number the model wrote as a number, and a
    list it wrote as JSON text, were rejected before any WDK call.
    """

    def test_numbers_and_json_lists_are_read(self) -> None:
        assert coerce_proposals(
            {
                "fold_change": 2,
                "adj_p_value": 1e-8,
                "organism": '["Plasmodium"]',
                "x": None,
            }
        ) == {
            "fold_change": "2",
            "adj_p_value": "1e-08",
            "organism": ["Plasmodium"],
            "x": None,
        }

    def test_a_string_and_a_real_list_are_unchanged(self) -> None:
        assert coerce_proposals(
            {"organism": "Plasmodium falciparum 3D7", "samples": ["20 Hour"]}
        ) == {"organism": "Plasmodium falciparum 3D7", "samples": ["20 Hour"]}

    def test_a_list_of_numbers_becomes_a_list_of_strings(self) -> None:
        assert coerce_proposals({"hours": [20, 21]}) == {"hours": ["20", "21"]}
        assert coerce_proposals({"hours": "[20, 21]"}) == {"hours": ["20", "21"]}

    def test_a_boolean_is_read_as_its_json_word(self) -> None:
        # A yes/no parameter has a vocabulary, so a boolean has to reach it as a
        # value rather than fail the schema.
        assert coerce_proposals({"is_syntenic": True, "is_pseudo": False}) == {
            "is_syntenic": "true",
            "is_pseudo": "false",
        }

    def test_a_nested_object_is_refused_naming_the_parameter(self) -> None:
        # A filter value travels as a JSON string, never as a bare object. The
        # retry has to say which parameter was written that way.
        with pytest.raises(ValueError, match="ngsSnp_strain_meta"):
            coerce_proposals({"ngsSnp_strain_meta": {"filters": []}})

    def test_the_annotation_reports_the_offending_parameter(self) -> None:
        adapter: TypeAdapter[ParamProposals] = TypeAdapter(ParamProposals)

        with pytest.raises(PydanticValidationError, match="ngsSnp_strain_meta"):
            adapter.validate_python({"ngsSnp_strain_meta": {"filters": []}})

    def test_bracketed_text_that_is_not_json_stays_text(self) -> None:
        assert coerce_proposals({"text_expression": "[unnamed]"}) == {
            "text_expression": "[unnamed]"
        }

    def test_a_non_mapping_passes_through_for_pydantic_to_reject(self) -> None:
        assert coerce_proposals("not a mapping") == "not a mapping"

    def test_the_annotation_validates_and_has_a_json_schema(self) -> None:
        # The annotation becomes the tool schema the model reads, so it has to
        # stay JSON-schema-friendly.
        adapter: TypeAdapter[ParamProposals] = TypeAdapter(ParamProposals)
        assert adapter.validate_python({"fold_change": 2}) == {"fold_change": "2"}
        assert adapter.json_schema()["type"] == "object"


class TestUnknownParameterErrorName:
    """The DAG's own name check still becomes a retry, as the backstop."""

    @pytest.mark.asyncio
    async def test_it_becomes_a_retry_listing_the_real_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        st = AgentToolState()

        async def _resolve(**_kw: object) -> ResolvedParams:
            raise UnknownParameterError(
                ["min_percentile"], ["min_expression_percentile"]
            )

        _serve(
            monkeypatch,
            lambda _context: [_pi("min_expression_percentile", required=False)],
        )
        _serve_bare_definition(monkeypatch)
        monkeypatch.setattr(frame_spec, "resolve_params_with_intent", _resolve)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)

        with pytest.raises(ModelRetry) as exc:
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="top 10 percent",
                search_name="GenesByMicroarray",
                params={"min_expression_percentile": "90"},
            )

        message = str(exc.value)
        assert "min_percentile" in message
        assert "min_expression_percentile" in message
        # The retry carries the names, so it must not send the model back for
        # the sheet: that is what tripled the sheet reads in one turn.
        assert "do not request the sheet again" in message
        assert "get_search_overview" not in message
        assert st.operational_spec_draft.criteria == []


def _pi(
    name: str,
    param_type: str = "string",
    *,
    required: bool = True,
    options: list[VocabOption] | None = None,
    default: str | None = None,
    depends_on: list[str] | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=param_type,
        required=required,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        vocab_leaves=options or [],
        vocab_depends_on=depends_on,
    )


def _numeric_pi(name: str, default: str, *, required: bool = True) -> ParameterInfo:
    """A numeric bound as WDK reports it: type string with isNumber true."""
    return ParameterInfo(
        name=name,
        display_name=name,
        type="string",
        required=required,
        is_visible=True,
        is_number=True,
        help="",
        value_format="",
        default_value=default,
    )


def _serve_bare_definition(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer both definition reads on the params path with a nameless definition.

    A test that asserts what was registered, or what the definition declares,
    serves the full one instead.
    """

    async def _details(
        record_type: str, name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        return WDKSearchResponse(
            searchData=WDKSearch(urlSegment=name),
            validation=StepValidation(level="NONE", is_valid=False),
        )

    client = MagicMock()
    client.get_search_details = _details
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)
    _serve_catalog_details(monkeypatch, [])


def _serve_and_resolve(monkeypatch: pytest.MonkeyPatch, at: ParamsAt) -> None:
    """Serve the parameters and run the real DAG walk over the tool's fetcher."""
    _serve(monkeypatch, at)
    _serve_bare_definition(monkeypatch)
    monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)


_ORGANISMS = [
    VocabOption(value="Plasmodium", display="Plasmodium"),
    VocabOption(value="Plasmodium falciparum 3D7", display="P. falciparum 3D7"),
]
_TEXT_FIELDS = [
    VocabOption(value="product", display="product"),
    VocabOption(value="Notes", display="Notes"),
]


def _genes_by_text(_context: dict[str, str]) -> list[ParameterInfo]:
    return [
        _pi("text_expression"),
        _pi("text_search_organism", "multi-pick-vocabulary", options=_ORGANISMS),
        _pi("document_type", required=False, default="gene"),
        _pi(
            "text_fields",
            "multi-pick-vocabulary",
            required=False,
            options=_TEXT_FIELDS,
            default='["product", "Notes"]',
        ),
    ]


class TestEveryVisibleRequiredParamIsDecided:
    @pytest.mark.asyncio
    async def test_a_missing_required_param_is_a_retry_naming_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={"text_expression": "kinase"},
            )

        assert "text_search_organism" in str(info.value)
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_null_binds_the_default_and_discloses_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)

        result = (
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["Plasmodium"],
                    "document_type": None,
                    "text_fields": None,
                },
            )
        ).return_value

        assert "document_type" in result.defaulted_params
        assert result.resolved_params["text_expression"] == "kinase"
        assert result.resolved_params["text_search_organism"] == '["Plasmodium"]'


_YES_NO = [
    VocabOption(value="yes", display="Yes"),
    VocabOption(value="no", display="No"),
]


def _yes_no(_context: dict[str, str]) -> list[ParameterInfo]:
    return [_pi("is_syntenic", "single-pick-vocabulary", options=_YES_NO)]


def _by_percentile(_context: dict[str, str]) -> list[ParameterInfo]:
    return [_numeric_pi("min_expression_percentile", "80")]


def _optional_percentile(_context: dict[str, str]) -> list[ParameterInfo]:
    return [_numeric_pi("min_expression_percentile", "80", required=False)]


class TestAStatedQuantityLeftNullIsARetry:
    """A number the criterion states is read, or the call comes back.

    Binding the search default here reports WDK's own threshold as the
    researcher's stated one, and nothing downstream can tell them apart.
    """

    @pytest.mark.asyncio
    async def test_a_stated_quantity_left_null_is_a_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _by_percentile)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="top 10 percent by expression",
                search_name="GenesByExpressionPercentile",
                params={"min_expression_percentile": None},
            )

        message = str(info.value)
        assert "min_expression_percentile" in message
        assert "Pass the stated value" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_an_optional_param_left_out_of_the_call_is_a_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An optional param needs no null, so nothing before resolution asks about
        # it. Left out, it runs on the search's own default and the stated number
        # never reaches WDK.
        _serve_and_resolve(monkeypatch, _optional_percentile)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="top 10 percent by expression",
                search_name="GenesByExpressionPercentile",
                params={},
            )

        assert "min_expression_percentile" in str(info.value)
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_the_stated_value_binds_and_is_not_a_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _by_percentile)
        st = AgentToolState()

        result = (
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="top 10 percent by expression",
                search_name="GenesByExpressionPercentile",
                params={"min_expression_percentile": "90"},
            )
        ).return_value

        assert result.resolved_params == {"min_expression_percentile": "90"}
        assert result.defaulted_params == []
        assert st.operational_spec_draft.criteria[0].id == "c1"

    @pytest.mark.asyncio
    async def test_a_criterion_stating_no_quantity_keeps_the_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _by_percentile)
        st = AgentToolState()

        result = (
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="highly expressed genes",
                search_name="GenesByExpressionPercentile",
                params={"min_expression_percentile": None},
            )
        ).return_value

        assert result.resolved_params == {"min_expression_percentile": "80"}
        assert result.defaulted_params == ["min_expression_percentile"]


class TestAProposedValueMustBeOnTheSheet:
    @pytest.mark.asyncio
    async def test_an_unknown_value_is_a_retry_with_the_nearest_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["Plasmodium falciprum 3D7"],
                    "document_type": None,
                    "text_fields": None,
                },
            )

        message = str(info.value)
        assert "text_search_organism" in message
        assert "Plasmodium falciparum 3D7" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_a_substring_of_an_entry_is_not_a_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # "falciparum" reads as one of two organisms under substring matching,
        # so the binding it produces is decided by vocabulary order.
        _serve_and_resolve(monkeypatch, _genes_by_text)

        with pytest.raises(ModelRetry):
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["falciparum"],
                    "document_type": None,
                    "text_fields": None,
                },
            )

    @pytest.mark.asyncio
    async def test_a_boolean_is_answered_with_the_nearest_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A yes/no vocabulary spells its entries "yes" and "no", so a boolean is
        # an unmatched value and the retry names the entry that was meant.
        _serve_and_resolve(monkeypatch, _yes_no)
        adapter: TypeAdapter[ParamProposals] = TypeAdapter(ParamProposals)

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="non-syntenic orthologs",
                search_name="GenesByOrthologs",
                params=adapter.validate_python({"is_syntenic": False}),
            )

        message = str(info.value)
        assert "'false'" in message
        assert "'no'" in message

    @pytest.mark.asyncio
    async def test_a_display_label_names_its_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)

        result = (
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["P. falciparum 3D7"],
                    "document_type": None,
                    "text_fields": None,
                },
            )
        ).return_value

        assert (
            result.resolved_params["text_search_organism"]
            == '["Plasmodium falciparum 3D7"]'
        )


_PFAM_DOMAINS = [
    VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase"),
    VocabOption(value="PF00569 : ZZ", display="PF00569 : ZZ"),
    VocabOption(value="PF00169 : PH", display="PF00169 : PH"),
    VocabOption(value="PF00560 : LRR_1", display="PF00560 : LRR_1"),
    VocabOption(value="PF00006 : ATP-synt_ab", display="PF00006 : ATP-synt_ab"),
]


def _by_domain(_context: dict[str, str]) -> list[ParameterInfo]:
    return [_pi("domain_typeahead", "single-pick-vocabulary", options=_PFAM_DOMAINS)]


class TestAnAccessionNamesItsEntry:
    @pytest.mark.asyncio
    async def test_an_accession_alone_binds_the_whole_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _by_domain)

        result = (
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinase domain genes",
                search_name="GenesByInterproDomain",
                params={"domain_typeahead": "PF00069"},
            )
        ).return_value

        assert result.resolved_params["domain_typeahead"] == "PF00069 : Pkinase"

    @pytest.mark.asyncio
    async def test_the_nearest_entries_lead_with_the_ones_the_value_starts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _by_domain)

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinase domain genes",
                search_name="GenesByInterproDomain",
                params={"domain_typeahead": "PF0006"},
            )

        message = str(info.value)
        assert message.index("PF00069 : Pkinase") < message.index("PF00569 : ZZ")

    @pytest.mark.asyncio
    async def test_an_accession_two_entries_share_says_which_two(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        shared = [
            VocabOption(value="PF00069 : Pkinase", display="PF00069 : Pkinase"),
            VocabOption(value="PF00069 : Pkinase_C", display="PF00069 : Pkinase_C"),
        ]
        _serve_and_resolve(
            monkeypatch,
            lambda _c: [
                _pi("domain_typeahead", "single-pick-vocabulary", options=shared)
            ],
        )

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinase domain genes",
                search_name="GenesByInterproDomain",
                params={"domain_typeahead": "PF00069"},
            )

        message = str(info.value)
        assert "share the accession" in message
        assert "PF00069 : Pkinase_C" in message


_AVERAGE_ONLY = [VocabOption(value="average1", display="average")]
_EVERY_AGGREGATION = [
    VocabOption(value="average1", display="average"),
    VocabOption(value="minimum2", display="minimum"),
    VocabOption(value="maximum2", display="maximum"),
]


def _aggregation_under_samples(context: dict[str, str]) -> list[ParameterInfo]:
    """The child's vocabulary opens up only once the samples are bound."""
    bound = "samples_generic" in context
    return [
        _pi(
            "samples_generic",
            "multi-pick-vocabulary",
            options=[VocabOption(value="sampleA", display="sampleA")],
        ),
        _pi(
            "min_max_avg_ref",
            "single-pick-vocabulary",
            options=_EVERY_AGGREGATION if bound else _AVERAGE_ONLY,
            default="average1",
            depends_on=["samples_generic"],
        ),
    ]


class TestADependentVocabularyIsRedecided:
    @pytest.mark.asyncio
    async def test_a_changed_vocabulary_comes_back_to_be_decided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()

        result = (
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="aggregate expression over the sampled patients",
                search_name="GenesByRNASeq",
                params={"samples_generic": ["sampleA"], "min_max_avg_ref": None},
            )
        ).return_value

        assert [entry.name for entry in result.redecide] == ["min_max_avg_ref"]
        fresh = [option.value for option in result.redecide[0].vocabulary]
        assert fresh == ["average1", "minimum2", "maximum2"]
        assert st.operational_spec_draft.criteria == [], "nothing is recorded yet"

    @pytest.mark.asyncio
    async def test_a_value_from_the_fresh_vocabulary_binds_as_stated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()

        result = (
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="aggregate expression over the sampled patients",
                search_name="GenesByRNASeq",
                params={"samples_generic": ["sampleA"], "min_max_avg_ref": "minimum2"},
            )
        ).return_value

        assert result.redecide == []
        assert result.resolved_params["min_max_avg_ref"] == "minimum2"
        assert "min_max_avg_ref" not in result.defaulted_params
        assert st.operational_spec_draft.criteria[0].id == "c1"

    @pytest.mark.asyncio
    async def test_an_unchanged_vocabulary_is_not_redecided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _genes_by_text)

        result = (
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["Plasmodium"],
                    "document_type": None,
                    "text_fields": None,
                },
            )
        ).return_value

        assert result.redecide == []


async def _aggregation_call(
    state: AgentToolState, params: ParamProposals
) -> SetCriterionResult:
    return (
        await set_criterion(
            _frame_ctx(state),
            criterion_id="c1",
            text="aggregate expression over the sampled patients",
            search_name="GenesByRNASeq",
            params=params,
        )
    ).return_value


class TestARedecidedParamIsDecidedOnce:
    """The re-call closes the question, whichever way the model answers it.

    A ``redecide`` is a successful return, so no retry budget bounds it. Asking
    again for a param the model was already shown leaves the criterion unbound
    for the whole turn.
    """

    @pytest.mark.asyncio
    async def test_the_same_null_binds_the_default_under_the_bound_parents(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()
        same = {"samples_generic": ["sampleA"], "min_max_avg_ref": None}

        first = await _aggregation_call(st, dict(same))
        second = await _aggregation_call(st, dict(same))

        assert [entry.name for entry in first.redecide] == ["min_max_avg_ref"]
        assert second.redecide == []
        assert second.resolved_params["min_max_avg_ref"] == "average1"
        assert "min_max_avg_ref" in second.defaulted_params
        assert st.operational_spec_draft.criteria[0].id == "c1"

    @pytest.mark.asyncio
    async def test_a_fresh_value_on_the_re_call_binds_as_stated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()

        await _aggregation_call(
            st, {"samples_generic": ["sampleA"], "min_max_avg_ref": None}
        )
        second = await _aggregation_call(
            st, {"samples_generic": ["sampleA"], "min_max_avg_ref": "minimum2"}
        )

        assert second.redecide == []
        assert second.resolved_params["min_max_avg_ref"] == "minimum2"
        assert "min_max_avg_ref" not in second.defaulted_params

    @pytest.mark.asyncio
    async def test_a_value_outside_the_fresh_vocabulary_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()

        await _aggregation_call(
            st, {"samples_generic": ["sampleA"], "min_max_avg_ref": None}
        )
        with pytest.raises(ModelRetry) as info:
            await _aggregation_call(
                st, {"samples_generic": ["sampleA"], "min_max_avg_ref": "median9"}
            )

        message = str(info.value)
        assert "min_max_avg_ref" in message
        assert "minimum2" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_the_ledger_is_kept_per_criterion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two criteria over the same search are two separate questions.
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()

        await _aggregation_call(
            st, {"samples_generic": ["sampleA"], "min_max_avg_ref": None}
        )
        other = (
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c2",
                text="a second aggregate criterion",
                search_name="GenesByRNASeq",
                params={"samples_generic": ["sampleA"], "min_max_avg_ref": None},
            )
        ).return_value

        assert [entry.name for entry in other.redecide] == ["min_max_avg_ref"]

    @pytest.mark.asyncio
    async def test_the_ledger_is_kept_per_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Searches share parameter names. Re-pointing a criterion at another
        # search asks the question again, over that search's own vocabulary.
        _serve_and_resolve(monkeypatch, _aggregation_under_samples)
        st = AgentToolState()

        await _aggregation_call(
            st, {"samples_generic": ["sampleA"], "min_max_avg_ref": None}
        )
        elsewhere = (
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="the same criterion on another search",
                search_name="GenesByRNASeqAlternative",
                params={"samples_generic": ["sampleA"], "min_max_avg_ref": None},
            )
        ).return_value

        assert [entry.name for entry in elsewhere.redecide] == ["min_max_avg_ref"]


class TestAProposalNamesARealParameter:
    @pytest.mark.asyncio
    async def test_an_unknown_name_is_refused_even_when_it_proposes_null(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A null is stripped before the DAG's own name check, so the tool has to
        # make this call itself or the parameter is silently never set.
        _serve_and_resolve(monkeypatch, _genes_by_text)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await set_criterion(
                _frame_ctx(st),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["Plasmodium"],
                    "document_type": None,
                    "text_fields": None,
                    "totally_bogus_name": None,
                },
            )

        message = str(info.value)
        assert "totally_bogus_name" in message
        assert "text_expression" in message
        assert st.operational_spec_draft.criteria == []


class TestTheSearchIsReadOncePerContext:
    @pytest.mark.asyncio
    async def test_the_default_context_is_fetched_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The name check, the DAG's first pass and the redecide baseline all
        # want the same expandParams payload.
        seen: list[dict[str, str]] = []

        def _counted(context: dict[str, str]) -> list[ParameterInfo]:
            seen.append(dict(context))
            return _aggregation_under_samples(context)

        _serve_and_resolve(monkeypatch, _counted)

        await _aggregation_call(
            AgentToolState(),
            {"samples_generic": ["sampleA"], "min_max_avg_ref": None},
        )

        assert [c for c in seen if not c] == [{}]


_PHYLETIC_TERMS = [
    WDKVocabTerm(("ALL", "Root", None)),
    WDKVocabTerm(("EUKA", "Eukaryota", None)),
    WDKVocabTerm(("MAMM", "Mammalia", None)),
    WDKVocabTerm(("hsap", "Homo sapiens REF", None)),
    WDKVocabTerm(("mmus", "Mus musculus", None)),
    WDKVocabTerm(("pfal", "Plasmodium falciparum 3D7", None)),
]
_PHYLETIC_INDENTS = [
    WDKVocabTerm(("EUKA", "1", None)),
    WDKVocabTerm(("MAMM", "2", None)),
    WDKVocabTerm(("hsap", "3", None)),
    WDKVocabTerm(("mmus", "3", None)),
    WDKVocabTerm(("pfal", "2", None)),
]

_PHYLETIC_DEFINITION: list[WDKParameter] = [
    WDKStringParam(
        name="profile_pattern", is_visible=False, initial_display_value="hsap=1T"
    ),
    WDKStringParam(name="included_species", allow_empty_value=True),
    WDKStringParam(name="excluded_species", allow_empty_value=True),
    WDKEnumParam(
        name="organism",
        type="multi-pick-vocabulary",
        vocabulary=[WDKVocabTerm(("Pf3D7", "P. falciparum 3D7", None))],
    ),
    WDKEnumParam(
        name="phyletic_term_map",
        type="multi-pick-vocabulary",
        vocabulary=_PHYLETIC_TERMS,
    ),
    WDKEnumParam(
        name="phyletic_indent_map",
        type="multi-pick-vocabulary",
        vocabulary=_PHYLETIC_INDENTS,
    ),
]


def _serve_catalog_details(
    monkeypatch: pytest.MonkeyPatch,
    params: list[WDKParameter],
    properties: dict[str, list[str]] | None = None,
) -> list[SearchContext]:
    """Answer the catalog's cached definition read, recording each call."""
    seen: list[SearchContext] = []

    async def _details(
        ctx: SearchContext, **_kw: object
    ) -> tuple[WDKSearchResponse, str]:
        seen.append(ctx)
        return (
            WDKSearchResponse(
                searchData=WDKSearch(
                    urlSegment=ctx.search_name,
                    parameters=params,
                    properties=properties or {},
                ),
                validation=StepValidation(level="NONE", is_valid=False),
            ),
            ctx.record_type,
        )

    monkeypatch.setattr(frame_spec, "fetch_search_details", _details)
    return seen


def _serve_phyletic(monkeypatch: pytest.MonkeyPatch) -> list[SearchContext]:
    """Serve GenesByOrthologPattern as both a sheet and a definition."""
    _serve(monkeypatch, lambda _context: format_param_info_typed(_PHYLETIC_DEFINITION))
    _serve_bare_definition(monkeypatch)
    monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
    return _serve_catalog_details(monkeypatch, _PHYLETIC_DEFINITION)


async def _phyletic_call(
    state: AgentToolState, params: dict[str, str | list[str] | None]
) -> SetCriterionResult:
    return (
        await set_criterion(
            _frame_ctx(state),
            criterion_id="c_ortho",
            text="present in P. falciparum, absent from mammals",
            search_name="GenesByOrthologPattern",
            params=params,
        )
    ).return_value


class TestThePhyleticPatternIsDerived:
    """The two species lists are the proposal; the pattern is never written.

    ``profile_pattern`` is hidden and required, so a call that does not derive it
    binds the published default, which matches no census and returns no genes.
    """

    @pytest.mark.asyncio
    async def test_the_lists_bind_the_pattern_and_their_canonical_codes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_phyletic(monkeypatch)
        st = AgentToolState()

        result = await _phyletic_call(
            st,
            {
                "organism": ["Pf3D7"],
                "included_species": "pfal",
                "excluded_species": "Mammalia",
            },
        )

        assert result.resolved_params["profile_pattern"] == "%hsap:N%mmus:N%pfal:Y%"
        assert result.resolved_params["included_species"] == "pfal"
        assert result.resolved_params["excluded_species"] == "MAMM"

    @pytest.mark.asyncio
    async def test_the_pattern_is_stated_and_is_no_open_slot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_phyletic(monkeypatch)
        st = AgentToolState()

        result = await _phyletic_call(
            st, {"organism": ["Pf3D7"], "included_species": "pfal"}
        )

        assert result.open_slots == []
        assert "profile_pattern" not in result.defaulted_params
        criterion = st.operational_spec_draft.criteria[0]
        assert to_wire(criterion.resolved_params["profile_pattern"]) == "%pfal:Y%"

    @pytest.mark.asyncio
    async def test_a_species_name_is_read_as_its_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_phyletic(monkeypatch)

        result = await _phyletic_call(
            AgentToolState(),
            {
                "organism": ["Pf3D7"],
                "included_species": "Plasmodium falciparum 3D7",
                "excluded_species": ["Homo sapiens REF"],
            },
        )

        assert result.resolved_params["profile_pattern"] == "%hsap:N%pfal:Y%"
        assert result.resolved_params["included_species"] == "pfal"

    @pytest.mark.asyncio
    async def test_an_unknown_species_is_a_retry_naming_the_nearest_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_phyletic(monkeypatch)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await _phyletic_call(
                st,
                {
                    "organism": ["Pf3D7"],
                    "included_species": "Plasmodium falciparum",
                    "excluded_species": None,
                },
            )

        message = str(info.value)
        assert "Plasmodium falciparum 3D7" in message
        assert "included_species" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_the_unresolved_retry_names_the_lookup_tool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A genus reads as a plausible node and is not one, so the retry says
        # where the real names come from rather than only that this one missed.
        _serve_phyletic(monkeypatch)

        with pytest.raises(ModelRetry) as info:
            await _phyletic_call(
                AgentToolState(),
                {"organism": ["Pf3D7"], "included_species": "Plasmodium"},
            )

        message = str(info.value)
        assert "A genus or common name is not a node" in message
        assert "lookup_phyletic_codes(query)" in message

    @pytest.mark.asyncio
    async def test_a_code_in_both_lists_is_a_retry_naming_the_conflict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_phyletic(monkeypatch)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await _phyletic_call(
                st,
                {
                    "organism": ["Pf3D7"],
                    "included_species": "pfal, hsap",
                    "excluded_species": "hsap",
                },
            )

        assert "hsap" in str(info.value)
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_two_empty_lists_are_a_retry_and_bind_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The bare wildcard is a valid pattern that constrains nothing, so it
        # would return every gene of the chosen organisms as a phyletic answer.
        _serve_phyletic(monkeypatch)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await _phyletic_call(
                st,
                {
                    "organism": ["Pf3D7"],
                    "included_species": None,
                    "excluded_species": None,
                },
            )

        message = str(info.value)
        assert "at least one species or clade" in message
        assert "included_species" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_naming_neither_list_is_the_same_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Both lists allow empty, so omitting them binds the hidden pattern to
        # its published default. Silence states no criterion just as two empty
        # lists do.
        _serve_phyletic(monkeypatch)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await _phyletic_call(st, {"organism": ["Pf3D7"]})

        message = str(info.value)
        assert "at least one species or clade" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_a_comma_list_is_not_refused_as_a_vocabulary_miss(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The canonical lists are comma-joined codes, which name no single
        # vocabulary entry.
        _serve_phyletic(monkeypatch)

        result = await _phyletic_call(
            AgentToolState(),
            {"organism": ["Pf3D7"], "excluded_species": "hsap, mmus"},
        )

        assert result.resolved_params["excluded_species"] == "hsap, mmus"
        assert result.resolved_params["profile_pattern"] == "%hsap:N%mmus:N%"

    @pytest.mark.asyncio
    async def test_naming_the_pattern_itself_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The pattern is hidden, so it is not a name the sheet offers.
        _serve_phyletic(monkeypatch)

        with pytest.raises(ModelRetry) as info:
            await _phyletic_call(
                AgentToolState(),
                {"organism": ["Pf3D7"], "profile_pattern": "%pfal:Y%"},
            )

        assert "profile_pattern" in str(info.value)

    @pytest.mark.asyncio
    async def test_a_search_with_no_species_list_derives_no_pattern(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # One cached definition read serves every derivation of the call, and a
        # search with no species list derives nothing from it.
        _serve(monkeypatch, _genes_by_text)
        monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
        _serve_bare_definition(monkeypatch)
        read = _serve_catalog_details(monkeypatch, _PHYLETIC_DEFINITION)
        registered = AgentToolState()
        registered.register_search(
            "GenesByText",
            SearchOverview(
                search_name="GenesByText",
                display_name="GenesByText",
                record_type="transcript",
                description="",
                parameter_names=[],
                required_params=[],
            ),
        )

        result = (
            await set_criterion(
                _frame_ctx(registered),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["Plasmodium"],
                    "document_type": None,
                    "text_fields": None,
                },
            )
        ).return_value

        assert result.resolved_params["text_expression"] == "kinase"
        assert "profile_pattern" not in result.resolved_params
        assert [c.search_name for c in read] == ["GenesByText"]

    @pytest.mark.asyncio
    async def test_the_derivation_reads_the_search_through_the_catalog(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The catalog memoizes the definition per record type and search, so the
        # derivation costs one read per process rather than one per call.
        read = _serve_phyletic(monkeypatch)

        await _phyletic_call(
            AgentToolState(), {"organism": ["Pf3D7"], "included_species": "pfal"}
        )

        assert [(c.record_type, c.search_name) for c in read] == [
            ("transcript", "GenesByOrthologPattern")
        ]


_EC_ENTRIES = ("2.7.-.-", "2.7.11.1", "3.4.21.-")

_EC_DEFINITION: list[WDKParameter] = [
    WDKEnumParam(
        name="ec_number_pattern",
        type="single-pick-vocabulary",
        initial_display_value="2.7.11.1",
        vocabulary=[WDKVocabTerm((v, v, None)) for v in _EC_ENTRIES],
    ),
    WDKStringParam(name="ec_wildcard", initial_display_value="N/A"),
]

_EC_PROPERTIES = {"radio-params": ["ec_number_pattern", "ec_wildcard"]}

_GO_TERM = "GO:0004672 : protein kinase activity"

_GO_DEFINITION: list[WDKParameter] = [
    WDKEnumParam(
        name="go_typeahead",
        type="multi-pick-vocabulary",
        display_type="typeAhead",
        initial_display_value="[]",
        vocabulary=[WDKVocabTerm((_GO_TERM, _GO_TERM, None))],
    ),
    WDKStringParam(name="go_term", initial_display_value="N/A"),
]

_GO_PROPERTIES = {"radio-params": ["go_typeahead", "go_term"]}


def _serve_ec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve GenesByEcNumber, whose two halves one query ORs."""
    _serve(monkeypatch, lambda _context: format_param_info_typed(_EC_DEFINITION))
    _serve_bare_definition(monkeypatch)
    monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
    _serve_catalog_details(monkeypatch, _EC_DEFINITION, _EC_PROPERTIES)


async def _ec_call(
    state: AgentToolState, params: dict[str, str | list[str] | None]
) -> SetCriterionResult:
    return (
        await set_criterion(
            _frame_ctx(state),
            criterion_id="c_ec",
            text="protein kinases",
            search_name="GenesByEcNumber",
            params=params,
        )
    ).return_value


def _serve_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve GenesByGoTerm, whose vocabulary half publishes a default it refuses."""
    _serve(monkeypatch, lambda _context: format_param_info_typed(_GO_DEFINITION))
    _serve_bare_definition(monkeypatch)
    monkeypatch.setattr(frame_spec, "validate_parameters", _noop_validate)
    _serve_catalog_details(monkeypatch, _GO_DEFINITION, _GO_PROPERTIES)


async def _go_call(
    state: AgentToolState, params: dict[str, str | list[str] | None]
) -> SetCriterionResult:
    return (
        await set_criterion(
            _frame_ctx(state),
            criterion_id="c_go",
            text="protein kinase activity",
            search_name="GenesByGoTerm",
            params=params,
        )
    ).return_value


class TestOneCriterionOfferedTwiceIsStatedOnce:
    """The vocabulary half carries the criterion and the free-text half is off.

    The two halves are ORed by one query, so a value in both widens the search,
    and neither half can be left empty.
    """

    @pytest.mark.asyncio
    async def test_a_free_text_wildcard_is_a_retry_naming_the_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_ec(monkeypatch)
        st = AgentToolState()

        with pytest.raises(ModelRetry) as info:
            await _ec_call(st, {"ec_number_pattern": None, "ec_wildcard": "2.7.*"})

        message = str(info.value)
        assert "2.7.-.-" in message
        assert "ec_number_pattern" in message
        assert "2.7.11.1" in message
        assert st.operational_spec_draft.criteria == []

    @pytest.mark.asyncio
    async def test_the_retry_names_the_vocabulary_read_for_a_wildcard(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A wildcard covers several entries, so the way back is a vocabulary
        # query rather than a value the model composes.
        _serve_ec(monkeypatch)

        with pytest.raises(ModelRetry) as info:
            await _ec_call(
                AgentToolState(),
                {"ec_number_pattern": None, "ec_wildcard": "*kinase*"},
            )

        message = str(info.value)
        assert "get_parameter_options" in message
        assert "N/A" in message

    @pytest.mark.asyncio
    async def test_the_retry_quotes_a_default_that_would_contribute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The EC vocabulary half publishes a real EC number, which the query ORs
        # in whatever the free text says.
        _serve_ec(monkeypatch)

        with pytest.raises(ModelRetry) as info:
            await _ec_call(
                AgentToolState(),
                {"ec_number_pattern": None, "ec_wildcard": "*protease*"},
            )

        assert "ec_number_pattern default 2.7.11.1 would still contribute" in str(
            info.value
        )

    @pytest.mark.asyncio
    async def test_the_retry_does_not_quote_a_default_the_search_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The GO vocabulary half publishes an empty list, which the search that
        # published it refuses, so there is no value to say would contribute.
        _serve_go(monkeypatch)

        with pytest.raises(ModelRetry) as info:
            await _go_call(
                AgentToolState(), {"go_typeahead": None, "go_term": "*kinase*"}
            )

        message = str(info.value)
        assert "go_typeahead cannot be left empty" in message
        assert "default" not in message
        assert _GO_TERM in message

    @pytest.mark.asyncio
    async def test_a_null_free_text_half_binds_off_and_opens_no_slot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve_ec(monkeypatch)
        st = AgentToolState()

        result = await _ec_call(
            st, {"ec_number_pattern": "2.7.-.-", "ec_wildcard": None}
        )

        assert result.resolved_params["ec_number_pattern"] == "2.7.-.-"
        assert result.resolved_params["ec_wildcard"] == "N/A"
        assert result.open_slots == []

    @pytest.mark.asyncio
    async def test_the_off_value_is_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The user's request never named it, so it is reported like any value
        # the call did not state.
        _serve_ec(monkeypatch)

        result = await _ec_call(
            AgentToolState(), {"ec_number_pattern": "2.7.-.-", "ec_wildcard": None}
        )

        assert "ec_wildcard" in result.defaulted_params

    @pytest.mark.asyncio
    async def test_a_search_declaring_no_pair_is_unaffected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The off value reaches only the free-text half of a declared pair.
        _serve_and_resolve(monkeypatch, _genes_by_text)

        result = (
            await set_criterion(
                _frame_ctx(AgentToolState()),
                criterion_id="c1",
                text="kinases",
                search_name="GenesByText",
                params={
                    "text_expression": "kinase",
                    "text_search_organism": ["Plasmodium"],
                    "document_type": None,
                    "text_fields": None,
                },
            )
        ).return_value

        assert "N/A" not in result.resolved_params.values()
