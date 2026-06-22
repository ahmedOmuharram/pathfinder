"""Integration tests for standalone plan tools (create, get, update, submit).

Uses real AgentToolState and AgentDeps — only RunContext is a mock wrapper.
"""

from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ConfigDict
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._plan_models import (
    DecisionOptionInput,
    PlanCreatedResponse,
    PlannedStepInput,
    StepPatch,
    UserQuestionInput,
    _apply_step_patches,
    _convert_step,
)
from pathfinder.ai.tools.standalone.plan import (
    create_plan,
    get_plan,
    update_plan,
)
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    SinglePickValue,
)
from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.pydantic_base import CamelModel


class _ProposedPlanView(CamelModel):
    model_config = ConfigDict(extra="ignore")

    root: StrategyStepNode


def _unwrap(result: Any) -> Any:
    """Unwrap ToolReturn for assertions.

    Tool results are now ``ToolReturn`` for success paths; error paths still
    return bare ``ToolErrorPayload`` instances. Tests that assert the
    ``return_value`` type should go through this helper.
    """
    if isinstance(result, ToolReturn):
        return result.return_value
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(
    site_id: str = "plasmodb",
    *,
    searches: tuple[str, ...] = ("GenesByTaxon", "GenesByLocation"),
) -> AgentDeps:
    session = StrategySession(site_id=site_id)
    state = AgentToolState()
    for name in searches:
        _register_search(state, name)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=state,
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _leaf_step(
    step_id: str = "step_a",
    search_name: str = "GenesByTaxon",
) -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name=search_name,
        display_name=f"Step: {search_name}",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={
            "organism": MultiPickValue(values=["Plasmodium falciparum 3D7"]),
        },
    )


def _combine_step(
    step_id: str = "step_combine",
    *,
    left_id: str = "step_a",
    right_id: str = "step_b",
) -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name="__combine__",
        display_name="Combine",
        record_type="transcript",
        step_type=StepType.COMBINE,
        operator="INTERSECT",
        left_id=left_id,
        right_id=right_id,
    )


def _register_search(
    state: AgentToolState, search_name: str, *, selected: bool = True
) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism"],
            required_params=["organism"],
            selection_status="selected" if selected else "candidate",
        ),
    )


# A minimal but realistic WDK-like spec map. ``_build_param`` refuses to
# synthesize a ``param_type="string"`` fallback (that would hide structured
# widget information from the frontend), so every param the LLM emits must
# have a real ``ParamSpecNormalized``.  We return a dict keyed by
# ``search_name`` whose values include the param names used by ``_leaf_step``.
_DEFAULT_ORGANISM_SPEC = ParamSpecNormalized(
    name="organism",
    param_type="multi-pick-vocabulary",
    display_type="treeBox",
    vocabulary=[
        WDKVocabTerm(("Plasmodium falciparum 3D7", "P. falciparum 3D7", None)),
        WDKVocabTerm(("Plasmodium vivax", "P. vivax", None)),
    ],
    help="Select one or more organisms",
    allow_empty_value=False,
)


@pytest.fixture(autouse=True)
def _stub_fetch_specs_by_search(monkeypatch: pytest.MonkeyPatch) -> None:
    canned_specs: dict[str, ParamSpecNormalized] = {
        "organism": _DEFAULT_ORGANISM_SPEC,
        "num_genes": ParamSpecNormalized(
            name="num_genes",
            param_type="number",
            is_number=True,
            min=1.0,
            max=10000.0,
            help="Number of genes to return",
        ),
    }

    async def _stub(
        site_id: str,
        steps: Iterable[PlannedStepInput],
    ) -> dict[str, dict[str, ParamSpecNormalized]]:
        out: dict[str, dict[str, ParamSpecNormalized]] = {}
        for step in steps:
            if step.step_type == StepType.COMBINE or not step.search_name:
                continue
            out[step.search_name] = dict(canned_specs)
        return out

    async def _stub_validate(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs.get("parameters") or {})

    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.plan._fetch_specs_by_search",
        _stub,
    )
    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.plan.validate_parameters",
        _stub_validate,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_plan_stores_plan_in_agent_state() -> None:
    """create_plan should set deps.agent_state.active_plan with correct counts."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    step_b = _leaf_step("step_b", "GenesByLocation")
    combine = _combine_step("step_c", left_id="step_a", right_id="step_b")

    result = await create_plan(
        ctx,
        title="Test Plan",
        description="Find genes by location and taxon",
        rationale="Intersect two gene sets",
        steps=[step_a, step_b, combine],
    )

    payload = _unwrap(result)
    assert isinstance(payload, PlanCreatedResponse)
    assert payload.title == "Test Plan"
    assert payload.step_count == 3

    plan = deps.agent_state.active_plan
    assert plan is not None
    assert plan.title == "Test Plan"
    assert len(plan.steps) == 3
    assert len(plan.connections) == 2
    assert plan.status == PlanStatus.DRAFT


@pytest.mark.asyncio
async def test_create_plan_proposed_tree_roots_at_terminal_combine() -> None:
    """The serialized proposedStrategyPlan (shown in the approval card) must
    root at the terminal combine — the step that feeds nothing — not at the
    first leaf. Regression: the root finder used ``to_step`` (receivers)
    instead of ``from_step`` (feeders), so every plan with a combine collapsed
    to a single leaf in the artifact while still executing the full tree."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    step_b = _leaf_step("step_b", "GenesByLocation")
    combine = _combine_step("step_c", left_id="step_a", right_id="step_b")

    result = await create_plan(
        ctx,
        title="Tree Plan",
        description="Intersect two gene sets",
        rationale="r",
        steps=[step_a, step_b, combine],
    )

    payload = _unwrap(result)
    assert isinstance(payload, PlanCreatedResponse)
    assert payload.planning_artifact is not None
    proposed = _ProposedPlanView.model_validate(
        payload.planning_artifact["proposedStrategyPlan"]
    )
    root = proposed.root
    assert root.operator == CombineOp.INTERSECT
    assert root.primary_input is not None
    assert root.secondary_input is not None
    assert root.primary_input.search_name == "GenesByTaxon"
    assert root.secondary_input.search_name == "GenesByLocation"


@pytest.mark.asyncio
async def test_create_plan_proposed_tree_preserves_nested_combines() -> None:
    """A nested plan ((a ∩ b) ∩ c) must serialize all combines, not collapse
    to one leaf. Mirrors the real 4-leaf/3-combine strategy that exposed the
    mis-rooting bug."""
    deps = _make_deps(
        searches=("GenesByTaxon", "GenesByLocation", "GenesByGoTerm"),
    )
    ctx = _make_ctx(deps)

    a = _leaf_step("step_a", "GenesByTaxon")
    b = _leaf_step("step_b", "GenesByLocation")
    c = _leaf_step("step_c", "GenesByGoTerm")
    inner = _combine_step("c_inner", left_id="step_a", right_id="step_b")
    outer = _combine_step("c_outer", left_id="c_inner", right_id="step_c")

    result = await create_plan(
        ctx,
        title="Nested",
        description="d",
        rationale="r",
        steps=[a, b, c, inner, outer],
    )

    payload = _unwrap(result)
    assert isinstance(payload, PlanCreatedResponse)
    assert payload.step_count == 5
    assert payload.planning_artifact is not None
    proposed = _ProposedPlanView.model_validate(
        payload.planning_artifact["proposedStrategyPlan"]
    )
    root = proposed.root
    assert root.operator == CombineOp.INTERSECT
    assert root.secondary_input is not None
    assert root.secondary_input.search_name == "GenesByGoTerm"
    assert root.primary_input is not None
    assert root.primary_input.operator == CombineOp.INTERSECT
    assert root.primary_input.primary_input is not None
    assert root.primary_input.primary_input.search_name == "GenesByTaxon"
    assert root.primary_input.secondary_input is not None
    assert root.primary_input.secondary_input.search_name == "GenesByLocation"


@pytest.mark.asyncio
async def test_create_plan_rejects_when_no_searches_discovered() -> None:
    """With an empty discovered universe (discovery never ran), a leaf plan
    must be rejected — planning has no real searches and would invent names."""
    deps = _make_deps(searches=())
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await create_plan(
            ctx,
            title="No discovery",
            description="d",
            rationale="r",
            steps=[_leaf_step("step_a", "GenesByRNASeqInvented")],
        )

    msg = str(excinfo.value)
    assert "discover" in msg.lower()
    assert "GenesByRNASeqInvented" in msg


@pytest.mark.asyncio
async def test_create_plan_suggests_close_match_for_unselected_search() -> None:
    """When discovery selected real searches, an invented near-miss name is
    rejected with a did-you-mean pointing at the real selected search."""
    deps = _make_deps(searches=("GenesByText",))
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await create_plan(
            ctx,
            title="Near miss",
            description="d",
            rationale="r",
            steps=[_leaf_step("step_a", "GeneByTextSearch")],
        )

    msg = str(excinfo.value)
    assert "GenesByText" in msg
    assert "GeneByTextSearch" in msg


@pytest.mark.asyncio
async def test_submit_plan_validates_topology() -> None:
    """submit_plan should reject a plan with a disconnected step reference."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    combine = _combine_step("step_c", left_id="step_a", right_id="step_ghost")

    with pytest.raises(ModelRetry) as excinfo:
        await create_plan(
            ctx,
            title="Bad Topology",
            description="This plan has a topology error",
            rationale="Testing",
            steps=[step_a, combine],
        )

    msg = str(excinfo.value)
    assert "TOPOLOGY_ERROR" in msg
    assert "step_ghost" in msg


@pytest.mark.asyncio
async def test_create_plan_rejects_invalid_param_value_with_structured_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps = _make_deps()
    ctx = _make_ctx(deps)

    async def _raising_validate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise ValidationError(
            title="Invalid parameter value",
            detail="Parameter 'organism' does not accept 'Bogus'.",
            errors=[
                {
                    "param": "organism",
                    "value": "Bogus",
                    "validOptions": ["Plasmodium falciparum 3D7", "Plasmodium vivax"],
                },
            ],
        )

    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.plan.validate_parameters",
        _raising_validate,
    )

    bad_step = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Step",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": MultiPickValue(values=["Bogus"])},
    )

    with pytest.raises(ModelRetry) as excinfo:
        await create_plan(
            ctx,
            title="Test",
            description="Bad params",
            rationale="r",
            steps=[bad_step],
        )

    msg = str(excinfo.value)
    assert "validOptions" in msg
    assert "Bogus" in msg
    assert "step_a" in msg


@pytest.mark.asyncio
async def test_create_plan_deduplicates_semantically_identical_questions() -> None:
    """create_plan should collapse duplicate questions into a single entry."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await create_plan(
        ctx,
        title="Question Plan",
        description="Tests duplicate questions",
        rationale="Avoid duplicate prompts",
        steps=[_leaf_step("step_a", "GenesByTaxon")],
        questions=[
            UserQuestionInput(
                question="Which organism should we use?",
                context="Pick the organism for the first step.",
                related_step="step_a",
                related_param="organism",
            ),
            UserQuestionInput(
                question="  Which organism should we use?  ",
                context="Pick the organism for the first step.",
                related_step="step_a",
                related_param="organism",
            ),
        ],
    )

    assert isinstance(_unwrap(result), PlanCreatedResponse)
    plan = deps.agent_state.active_plan
    assert plan is not None
    assert len(plan.questions) == 1
    assert plan.questions[0].question == "Which organism should we use?"


@pytest.mark.asyncio
async def test_update_plan_reuses_existing_question_and_preserves_answer() -> None:
    """update_plan should merge duplicate questions instead of appending them."""
    deps = _make_deps()
    ctx = _make_ctx(deps)
    _register_search(deps.agent_state, "GenesByTaxon")

    create_result = await create_plan(
        ctx,
        title="Question Merge Plan",
        description="Tests submit-time question dedupe",
        rationale="Avoid repeated approvals",
        steps=[_leaf_step("step_a", "GenesByTaxon")],
        questions=[
            UserQuestionInput(
                question="Which organism should we use?",
                context="Pick the organism for the first step.",
                related_step="step_a",
                related_param="organism",
            ),
        ],
    )

    assert isinstance(_unwrap(create_result), PlanCreatedResponse)
    plan = deps.agent_state.active_plan
    assert plan is not None
    original_question_id = plan.questions[0].id
    plan.questions[0].answer = "Plasmodium vivax"

    update_result = await update_plan(
        ctx,
        questions=[
            UserQuestionInput(
                question="Which organism should we use?",
                context="Pick the organism for the first step.",
                related_step="step_a",
                related_param="organism",
                options=[
                    DecisionOptionInput(
                        label="Plasmodium vivax",
                        description="Use the vivax organism context.",
                    ),
                ],
            ),
        ],
    )

    update_plan_payload = _unwrap(update_result)
    assert isinstance(update_plan_payload, StrategyPlan)
    assert len(update_plan_payload.questions) == 1
    assert update_plan_payload.questions[0].id == original_question_id
    assert update_plan_payload.questions[0].answer == "Plasmodium vivax"
    assert update_plan_payload.questions[0].options is not None
    assert update_plan_payload.questions[0].options[0].label == "Plasmodium vivax"


@pytest.mark.asyncio
async def test_update_plan_applies_step_patches() -> None:
    """update_plan with a StepPatch should modify the step's parameter."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    await create_plan(
        ctx,
        title="Original Plan",
        description="Original description",
        rationale="Original rationale",
        steps=[step_a],
    )

    plan_before = deps.agent_state.active_plan
    assert plan_before is not None
    assert plan_before.version == 1

    # Apply a patch with a JSON-encoded list — the StepPatch validator
    # auto-unwraps this into a real list (WDK rejects the stringified form).
    patch = StepPatch(
        step_id="step_a",
        parameters={"organism": MultiPickValue(values=["Plasmodium vivax"])},
    )

    result = await update_plan(ctx, step_updates=[patch])

    payload = _unwrap(result)
    assert isinstance(payload, StrategyPlan)
    assert payload.version == 2

    # Verify the parameter was unwrapped to a real list.
    patched_step = payload.steps[0]
    assert patched_step.id == "step_a"
    organism = next(p for p in patched_step.parameters if p.name == "organism")
    assert organism.value == MultiPickValue(values=["Plasmodium vivax"])
    assert organism.status == ParamStatus.SET


def _interpro_step_with_two_params() -> PlannedStep:
    return PlannedStep(
        id="s1",
        search_name="GenesByInterproDomain",
        display_name="InterPro kinase",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="organism",
                display_name="organism",
                param_type="multi-pick-vocabulary",
                value=MultiPickValue(values=["Plasmodium"]),
                status=ParamStatus.SET,
                required=True,
            ),
            PlannedParameter(
                name="domain_database",
                display_name="domain_database",
                param_type="single-pick-vocabulary",
                value=SinglePickValue(value="PFAM"),
                status=ParamStatus.SET,
                required=True,
            ),
        ],
    )


_GO_SPECS: dict[str, dict[str, ParamSpecNormalized]] = {
    "GenesByGoTerm": {
        "organism": _DEFAULT_ORGANISM_SPEC,
        "go_typeahead": ParamSpecNormalized(
            name="go_typeahead",
            param_type="multi-pick-vocabulary",
            help="GO term ids",
            allow_empty_value=False,
        ),
    },
}


def test_apply_step_patches_search_name_change_clears_stale_params() -> None:
    """Swapping a leaf step's search_name must drop the old search's params —
    they don't exist on the new search and WDK rejects them as unknown. Lead
    repro: replacing an InterPro kinase step with GenesByGoTerm left
    domain_database behind and every retry failed 'Unknown parameter'."""
    plan = StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[_interpro_step_with_two_params()],
        connections=[],
    )
    patch = StepPatch(
        step_id="s1",
        search_name="GenesByGoTerm",
        parameters={
            "organism": MultiPickValue(values=["Plasmodium"]),
            "go_typeahead": MultiPickValue(values=["GO:0004672"]),
        },
    )
    _apply_step_patches(plan, [patch], specs_by_search=_GO_SPECS)

    step = plan.steps[0]
    assert step.search_name == "GenesByGoTerm"
    assert {p.name for p in step.parameters} == {"organism", "go_typeahead"}


def test_apply_step_patches_param_only_merges_without_clearing() -> None:
    """A patch that does NOT change search_name keeps existing params (the
    additive/merge behavior for normal threshold tweaks)."""
    plan = StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[_interpro_step_with_two_params()],
        connections=[],
    )
    patch = StepPatch(
        step_id="s1",
        parameters={"organism": MultiPickValue(values=["Plasmodium vivax"])},
    )
    _apply_step_patches(plan, [patch])

    step = plan.steps[0]
    assert step.search_name == "GenesByInterproDomain"
    assert {p.name for p in step.parameters} == {"organism", "domain_database"}


@pytest.mark.asyncio
async def test_update_plan_accepts_and_applies_rationale() -> None:
    """update_plan tolerates a top-level ``rationale`` (the model naturally
    supplies one to explain the edit) and applies it to the plan instead of
    rejecting the call with extra_forbidden — which caused 4.1-mini to loop."""
    deps = _make_deps()
    ctx = _make_ctx(deps)
    await create_plan(
        ctx,
        title="P",
        description="d",
        rationale="original rationale",
        steps=[_leaf_step("step_a", "GenesByTaxon")],
    )

    result = await update_plan(
        ctx,
        rationale="switched kinase basis to GO molecular function",
    )
    payload = _unwrap(result)
    assert isinstance(payload, StrategyPlan)
    assert payload.rationale == "switched kinase basis to GO molecular function"


@pytest.mark.asyncio
async def test_get_plan_returns_active_plan() -> None:
    """get_plan should return the same plan that create_plan stored."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    create_result = await create_plan(
        ctx,
        title="My Plan",
        description="Test plan",
        rationale="Testing get_plan",
        steps=[step_a],
    )
    create_payload = _unwrap(create_result)
    assert isinstance(create_payload, PlanCreatedResponse)

    get_result = await get_plan(ctx)

    assert isinstance(get_result, StrategyPlan)
    assert get_result.title == "My Plan"
    assert get_result.id == create_payload.plan_id
    assert len(get_result.steps) == 1
    assert get_result.steps[0].search_name == "GenesByTaxon"


@pytest.mark.asyncio
async def test_get_plan_returns_error_when_no_plan() -> None:
    """get_plan should raise ModelRetry when no plan exists."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await get_plan(ctx)

    assert "NO_ACTIVE_PLAN" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_plan_returns_error_when_no_plan() -> None:
    """update_plan should raise ModelRetry when no plan exists."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await update_plan(ctx, title="New Title")

    assert "NO_ACTIVE_PLAN" in str(excinfo.value)


@pytest.mark.asyncio
async def test_create_plan_archives_previous_plan() -> None:
    """Creating a second plan should archive the first."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    await create_plan(
        ctx,
        title="Plan 1",
        description="First plan",
        rationale="Testing archival",
        steps=[step_a],
    )

    first_plan = deps.agent_state.active_plan
    assert first_plan is not None
    assert first_plan.title == "Plan 1"
    assert len(deps.agent_state.plan_history) == 0

    step_b = _leaf_step("step_b", "GenesByLocation")
    await create_plan(
        ctx,
        title="Plan 2",
        description="Second plan",
        rationale="Replaced first",
        steps=[step_b],
    )

    second_plan = deps.agent_state.active_plan
    assert second_plan is not None
    assert second_plan.title == "Plan 2"
    assert len(deps.agent_state.plan_history) == 1
    assert deps.agent_state.plan_history[0].title == "Plan 1"


# ---------------------------------------------------------------------------
# Parameter type enrichment from WDK specs
# ---------------------------------------------------------------------------


def test_convert_step_uses_real_param_type_from_specs() -> None:
    """_convert_step should use the WDK spec param_type, not hardcode 'string'."""
    step_input = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={
            "organism": MultiPickValue(values=["Plasmodium falciparum 3D7"]),
        },
    )
    specs = {
        "organism": ParamSpecNormalized(
            name="organism",
            param_type="multi-pick-vocabulary",
            display_type="treeBox",
            help="Select one or more organisms",
            allow_empty_value=False,
            dependent_params=("geneBooleanFilter",),
        ),
    }

    result = _convert_step(step_input, param_specs=specs)

    param = next(p for p in result.parameters if p.name == "organism")
    assert param.param_type == "multi-pick-vocabulary"
    assert param.description == "Select one or more organisms"
    assert param.depends_on == ["geneBooleanFilter"]
    assert param.required is True


def test_convert_step_populates_constraints_and_options_from_spec() -> None:
    """_convert_step should transfer vocabulary, display_type, and numeric metadata."""
    step_input = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={
            "organism": MultiPickValue(values=["pfal"]),
            "num_genes": NumberValue(value=100),
        },
    )
    specs = {
        "organism": ParamSpecNormalized(
            name="organism",
            param_type="multi-pick-vocabulary",
            display_type="treeBox",
            vocabulary=[
                WDKVocabTerm(("pfal", "P. falciparum", None)),
                WDKVocabTerm(("pvivax", "P. vivax", None)),
            ],
        ),
        "num_genes": ParamSpecNormalized(
            name="num_genes",
            param_type="number",
            is_number=True,
            min=1.0,
            max=10000.0,
            increment=1.0,
        ),
    }

    result = _convert_step(step_input, param_specs=specs)
    by_name = {p.name: p for p in result.parameters}

    org = by_name["organism"]
    assert org.options == ["pfal", "pvivax"]
    assert org.constraints is not None
    assert org.constraints["displayType"] == "treeBox"

    num = by_name["num_genes"]
    assert num.constraints is not None
    assert num.constraints["isNumber"] is True
    assert num.constraints["min"] == 1.0
    assert num.constraints["max"] == 10000.0
    assert num.constraints["increment"] == 1.0


def test_apply_step_patches_uses_specs_for_new_params() -> None:
    """_apply_step_patches should use WDK spec param_type for newly added params."""
    step_input = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": MultiPickValue(values=["pfal"])},
    )
    organism_spec = ParamSpecNormalized(
        name="organism",
        param_type="multi-pick-vocabulary",
        display_type="treeBox",
        help="Pick an organism",
    )
    plan = StrategyPlan(
        title="Test",
        description="Test",
        rationale="Test",
        steps=[_convert_step(step_input, param_specs={"organism": organism_spec})],
        connections=[],
    )

    specs = {
        "GenesByTaxon": {
            "num_genes": ParamSpecNormalized(
                name="num_genes",
                param_type="number",
                is_number=True,
                min=1.0,
                max=1000.0,
                help="Number of genes to return",
            ),
        },
    }

    patches = [
        StepPatch(
            step_id="step_a",
            parameters={"num_genes": NumberValue(value=100)},
        )
    ]
    _apply_step_patches(plan, patches, specs_by_search=specs)

    param = next(p for p in plan.steps[0].parameters if p.name == "num_genes")
    assert param.param_type == "number"
    assert param.description == "Number of genes to return"
