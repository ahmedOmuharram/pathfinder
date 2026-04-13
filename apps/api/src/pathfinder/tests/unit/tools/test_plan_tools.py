"""Integration tests for standalone plan tools (create, get, update, submit).

Uses real AgentToolState and AgentDeps — only RunContext is a mock wrapper.
"""

from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._plan_models import (
    DecisionOptionInput,
    PlanCreatedResponse,
    PlannedConnectionInput,
    PlannedStepInput,
    StepPatch,
    UserQuestionInput,
    _apply_step_patches,
    _convert_step,
)
from pathfinder.ai.tools.standalone.plan import (
    create_plan,
    get_plan,
    submit_plan,
    update_plan,
)
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlanStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload


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


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    session = StrategySession(site_id=site_id)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
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
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
    )


def _combine_step(step_id: str = "step_combine") -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name="__combine__",
        display_name="Combine",
        record_type="transcript",
        step_type=StepType.COMBINE,
        operator="INTERSECT",
    )


def _connection(from_step: str, to_step: str) -> PlannedConnectionInput:
    return PlannedConnectionInput(
        from_step=from_step,
        to_step=to_step,
        input_type="primary",
    )


def _register_search(state: AgentToolState, search_name: str) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism"],
            required_params=["organism"],
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
        {"value": "Plasmodium falciparum 3D7", "label": "P. falciparum 3D7"},
        {"value": "Plasmodium vivax", "label": "P. vivax"},
    ],
    help="Select one or more organisms",
    allow_empty_value=False,
)


@pytest.fixture(autouse=True)
def _stub_fetch_specs_by_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``_fetch_specs_by_search`` with a deterministic stub.

    Unit tests must not hit live WDK. The stub returns a spec map for
    every referenced search containing canned specs for the param names
    the helpers use (``organism`` for ``_leaf_step``, ``num_genes`` for
    patch tests).
    """
    canned_specs: dict[str, ParamSpecNormalized] = {
        "organism": _DEFAULT_ORGANISM_SPEC,
        "num_genes": ParamSpecNormalized(
            name="num_genes",
            param_type="number",
            is_number=True,
            min_value=1.0,
            max_value=10000.0,
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

    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.plan._fetch_specs_by_search", _stub,
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
    combine = _combine_step("step_c")
    connections = [
        _connection("step_a", "step_c"),
        _connection("step_b", "step_c"),
    ]

    result = await create_plan(
        ctx,
        title="Test Plan",
        description="Find genes by location and taxon",
        rationale="Intersect two gene sets",
        steps=[step_a, step_b, combine],
        connections=connections,
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
async def test_submit_plan_validates_topology() -> None:
    """submit_plan should reject a plan with a disconnected step reference."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    # Connection references a non-existent step "step_ghost"
    bad_connection = _connection("step_a", "step_ghost")

    result = await create_plan(
        ctx,
        title="Bad Topology",
        description="This plan has a topology error",
        rationale="Testing",
        steps=[step_a],
        connections=[bad_connection],
    )

    # create_plan itself catches topology errors
    assert isinstance(result, ToolErrorPayload)
    assert result.code == "TOPOLOGY_ERROR"
    assert "step_ghost" in result.message


@pytest.mark.asyncio
async def test_submit_plan_validates_parameters() -> None:
    """submit_plan should reject when a leaf step has unset required params."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    # Create a step with an explicitly NEEDS_DISCOVERY param
    step_a = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={},  # No parameters set
    )

    # First create the plan
    create_result = await create_plan(
        ctx,
        title="Missing Params Plan",
        description="This plan has missing parameters",
        rationale="Testing parameter validation",
        steps=[step_a],
        connections=[],
    )
    assert isinstance(_unwrap(create_result), PlanCreatedResponse)

    # Manually mark a required parameter as NEEDS_DISCOVERY to trigger validation
    plan = deps.agent_state.active_plan
    assert plan is not None
    plan.steps[0].parameters["organism"] = plan.steps[0].parameters.get(
        "organism",
        # Add a required param that is not set
        __import__(
            "pathfinder.domain.strategy.plan", fromlist=["PlannedParameter"]
        ).PlannedParameter(
            name="organism",
            display_name="Organism",
            param_type="string",
            value=None,
            status=ParamStatus.NEEDS_DISCOVERY,
            required=True,
        ),
    )

    submit_result = await submit_plan(ctx)

    assert isinstance(submit_result, ToolErrorPayload)
    assert submit_result.code == "PARAMETER_ERROR"
    assert "organism" in submit_result.message


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
        connections=[],
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
        connections=[],
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
        connections=[],
    )

    plan_before = deps.agent_state.active_plan
    assert plan_before is not None
    assert plan_before.version == 1

    # Apply a patch to change the organism parameter
    patch = StepPatch(
        step_id="step_a",
        parameters={"organism": '["Plasmodium vivax"]'},
    )

    result = await update_plan(ctx, step_updates=[patch])

    payload = _unwrap(result)
    assert isinstance(payload, StrategyPlan)
    assert payload.version == 2

    # Verify the parameter was actually changed
    patched_step = payload.steps[0]
    assert patched_step.id == "step_a"
    assert patched_step.parameters["organism"].value == '["Plasmodium vivax"]'
    assert patched_step.parameters["organism"].status == ParamStatus.SET


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
        connections=[],
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
    """get_plan should return a ToolErrorPayload when no plan exists."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await get_plan(ctx)

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "NO_ACTIVE_PLAN"


@pytest.mark.asyncio
async def test_update_plan_returns_error_when_no_plan() -> None:
    """update_plan should return a ToolErrorPayload when no plan exists."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await update_plan(ctx, title="New Title")

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "NO_ACTIVE_PLAN"


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
        connections=[],
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
        connections=[],
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
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
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

    param = result.parameters["organism"]
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
            "organism": '["pfal"]',
            "num_genes": "100",
        },
    )
    specs = {
        "organism": ParamSpecNormalized(
            name="organism",
            param_type="multi-pick-vocabulary",
            display_type="treeBox",
            vocabulary=[
                {"value": "pfal", "label": "P. falciparum"},
                {"value": "pvivax", "label": "P. vivax"},
            ],
        ),
        "num_genes": ParamSpecNormalized(
            name="num_genes",
            param_type="number",
            is_number=True,
            min_value=1.0,
            max_value=10000.0,
            increment=1.0,
        ),
    }

    result = _convert_step(step_input, param_specs=specs)

    # Vocabulary param should have options extracted.
    org = result.parameters["organism"]
    assert org.options == ["pfal", "pvivax"]
    assert org.constraints is not None
    assert org.constraints["displayType"] == "treeBox"

    # Number param should have numeric constraints.
    num = result.parameters["num_genes"]
    assert num.constraints is not None
    assert num.constraints["isNumber"] is True
    assert num.constraints["minValue"] == 1.0
    assert num.constraints["maxValue"] == 10000.0
    assert num.constraints["increment"] == 1.0


def test_apply_step_patches_uses_specs_for_new_params() -> None:
    """_apply_step_patches should use WDK spec param_type for newly added params."""
    step_input = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": "pfal"},
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
                min_value=1.0,
                max_value=1000.0,
                help="Number of genes to return",
            ),
        },
    }

    patches = [StepPatch(step_id="step_a", parameters={"num_genes": "100"})]
    _apply_step_patches(plan, patches, specs_by_search=specs)

    param = plan.steps[0].parameters["num_genes"]
    assert param.param_type == "number"
    assert param.description == "Number of genes to return"
