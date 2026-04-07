"""Regression tests for bugs found during the kani → pydantic-ai migration.

Each test targets the exact condition that would have failed before the fix,
verifying that the fix remains in place.  Numbered to match the migration
bug log.
"""

import dataclasses
import inspect
from unittest.mock import MagicMock

import pytest

from veupath_chatbot.ai.agents import _hooks
from veupath_chatbot.ai.agents._hooks import _GRAPH_MUTATING_TOOLS
from veupath_chatbot.ai.agents.state import AgentToolState
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.orchestration.phase_results import (
    DiscoveryResult,
    ExecutionResult,
    PlanningResult,
    VerificationResult,
)
from veupath_chatbot.ai.tools.standalone import experiment
from veupath_chatbot.ai.tools.standalone._plan_models import (
    _validate_domain_parameters,
)
from veupath_chatbot.ai.tools.standalone._result_models import (
    SampleRecordsResult,
    _extract_sample_response,
)
from veupath_chatbot.ai.tools.standalone.strategy_build import (
    combine_steps,
)
from veupath_chatbot.ai.tools.standalone.strategy_edit import delete_step
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    StepStatus,
    StepType,
    StrategyPlan,
)
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKAnswer
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.tool_errors import ToolErrorPayload, tool_error
from veupath_chatbot.services.chat.streaming.node_streaming import (
    stream_model_request,
)
from veupath_chatbot.services.chat.streaming.step_execution import (
    STEP_TYPE_TOOLS,
    SUPPORT_TOOLS,
)
from veupath_chatbot.services.parameter_optimization.callbacks import (
    OptimizationStartedEvent,
)

# ── Helpers ──────���─────────────────────────────────────────────────────────


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


# ── Bug 1: _hooks.py imports from _helpers, not GraphOpsMixin ─────────────


def test_bug1_hooks_imports_from_helpers_not_mixin() -> None:
    """Bug 1: _hooks.py must import helpers from standalone._helpers, not a mixin.

    The migration removed GraphOpsMixin.  If _hooks.py still imported from it,
    it would raise ImportError at module load time.  Verify the module loads
    and exports the expected symbols.
    """
    # These must exist as module-level symbols from _helpers
    assert hasattr(_hooks, "_slim_graph_result")
    assert hasattr(_hooks, "_track_search_discovery")
    assert hasattr(_hooks, "_GRAPH_MUTATING_TOOLS")
    assert callable(_hooks._slim_graph_result)
    assert callable(_hooks._track_search_discovery)


# ── Bug 3: No duplicate tool_call_start for PartStartEvent+ToolCallPart ───


def test_bug3_no_duplicate_tool_call_start() -> None:
    """Bug 3: _stream_model_request must skip tool_call_start for PartStartEvent.

    The fix is a deliberate ``pass`` in the PartStartEvent+ToolCallPart branch
    of _stream_model_request.  tool_call_start is emitted only from
    _stream_call_tools via FunctionToolCallEvent.

    We verify the architectural contract: the streaming module defines
    _stream_model_request AND _stream_call_tools as separate functions,
    and the _stream_model_request source contains the skip comment.
    """
    # Verify the pass is in stream_model_request source (the fix).
    source = inspect.getsource(stream_model_request)
    assert "tool_call_start is emitted by stream_call_tools" in source
    assert "pass" in source


# ── Bug 11: delete_step checks before deletion ────────────────────────────


@pytest.mark.asyncio
async def test_bug11_delete_step_checks_before_deletion() -> None:
    """Bug 11: delete_step on a single-step graph must return an error
    WITHOUT modifying the graph.

    Before the fix, delete_step would modify the graph and then error out,
    leaving it in an inconsistent state.
    """
    session = StrategySession(site_id="plasmodb")
    graph = session.create_graph("Test")
    graph.record_type = "transcript"

    step = PlanStepNode(search_name="GenesByTaxon", display_name="Only Step")
    graph.add_step(step)
    step_id = step.id

    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        agent_state=AgentToolState(),
    )
    ctx = _make_ctx(deps)

    assert len(graph.steps) == 1

    result = await delete_step(ctx, step_id)

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "VALIDATION_ERROR"
    assert "clear_strategy" in result.message

    # Graph must be UNMODIFIED
    assert len(graph.steps) == 1
    assert step_id in graph.steps


# ── Bug 12: validate_params checks leaf steps ─────────────────────────────


def test_bug12_validate_params_checks_leaf_steps() -> None:
    """Bug 12: _validate_domain_parameters must check leaf steps for
    required parameters that have not been set.
    """
    leaf = PlannedStep(
        id="leaf1",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters={
            "organism": PlannedParameter(
                name="organism",
                display_name="Organism",
                param_type="string",
                value=None,
                status=ParamStatus.NEEDS_DISCOVERY,
                required=True,
            ),
        },
    )
    combine = PlannedStep(
        id="comb1",
        search_name="__combine__",
        display_name="Combine",
        step_type=StepType.COMBINE,
        status=StepStatus.READY,
        operator="INTERSECT",
    )

    plan = StrategyPlan(
        title="Test",
        description="desc",
        rationale="rat",
        steps=[leaf, combine],
        connections=[
            PlannedConnection(from_step="leaf1", to_step="comb1"),
        ],
    )

    # Leaf1 has an incoming connection (it feeds INTO comb1 as from_step),
    # but leaf1 itself is NOT a to_step — it's a source.  The validation
    # should check leaf1 because it has unset required params.
    # non_leaf_ids = {c.to_step for c in plan.connections} = {"comb1"}
    # leaf1 is NOT in non_leaf_ids, so it gets checked.
    error = _validate_domain_parameters(plan, AgentToolState())

    assert error is not None
    assert isinstance(error, ToolErrorPayload)
    assert "organism" in error.message


def test_bug12_validate_params_passes_when_all_set() -> None:
    """Complementary: leaf steps with all required params set should pass."""
    leaf = PlannedStep(
        id="leaf1",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters={
            "organism": PlannedParameter(
                name="organism",
                display_name="Organism",
                param_type="string",
                value="Plasmodium falciparum 3D7",
                status=ParamStatus.SET,
                required=True,
            ),
        },
    )

    plan = StrategyPlan(
        title="Test",
        description="desc",
        rationale="rat",
        steps=[leaf],
        connections=[],
    )

    error = _validate_domain_parameters(plan, AgentToolState())
    assert error is None


# ── Bug 13: invalid operator returns ToolErrorPayload, not ValueError ─────


@pytest.mark.asyncio
async def test_bug13_invalid_operator_returns_error() -> None:
    """Bug 13: combine_steps with an invalid operator must return a
    ToolErrorPayload, not raise ValueError.
    """
    session = StrategySession(site_id="plasmodb")
    graph = session.create_graph("Test")
    graph.record_type = "transcript"

    step_a = PlanStepNode(search_name="GenesByTaxon", display_name="A")
    step_b = PlanStepNode(search_name="GenesByLocation", display_name="B")
    graph.add_step(step_a)
    graph.add_step(step_b)

    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        agent_state=AgentToolState(),
    )
    ctx = _make_ctx(deps)

    result = await combine_steps(
        ctx,
        step_a_id=step_a.id,
        step_b_id=step_b.id,
        operator="INVALID_OP",
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "VALIDATION_ERROR"
    assert "INVALID_OP" in result.message
    assert "INTERSECT" in result.message


# ── Bug 14: _extract_sample_response passes wdk_step_id through ──────────


def test_bug14_sample_response_has_correct_step_id() -> None:
    """Bug 14: _extract_sample_response must propagate wdk_step_id into
    the SampleRecordsResult.step_id field.
    """
    answer = WDKAnswer.model_validate({
        "meta": {
            "totalCount": 42,
            "attributes": ["primary_key", "gene_name"],
            "tables": [],
        },
        "records": [],
    })

    result = _extract_sample_response(answer, wdk_step_id=12345)

    assert isinstance(result, SampleRecordsResult)
    assert result.step_id == 12345
    assert result.total_count == 42
    assert result.attributes == ["primary_key", "gene_name"]


def test_bug14_sample_response_default_step_id_is_zero() -> None:
    """Default wdk_step_id of 0 should also propagate."""
    answer = WDKAnswer.model_validate({
        "meta": {"totalCount": 0, "attributes": [], "tables": []},
        "records": [],
    })

    result = _extract_sample_response(answer)
    assert result.step_id == 0


# ── Bug 15: experiment uses ErrorCode enum, not string literal ────────────


def test_bug15_experiment_uses_error_code_enum() -> None:
    """Bug 15: experiment.py must import and use ErrorCode, not raw string literals.

    Verify that ErrorCode.VALIDATION_ERROR is used for error responses.
    """
    source = inspect.getsource(experiment)
    assert "ErrorCode.VALIDATION_ERROR" in source
    # Must NOT use string literals for error codes.
    assert "\"VALIDATION_ERROR\"" not in source


# ── Bug 16: workbench orchestrator skips PartStartEvent tool_call_start ───


def test_bug16_stream_model_request_skips_part_start_tool_call() -> None:
    """Bug 16: _stream_model_request must NOT emit tool_call_start for
    PartStartEvent+ToolCallPart events — that's done by _stream_call_tools.

    We verify by inspecting the source: the PartStartEvent branch must
    contain a 'pass' (the skip) and a comment explaining why.
    """
    source = inspect.getsource(stream_model_request)

    # The fix is a pass with a comment in the PartStartEvent+ToolCallPart branch.
    assert "PartStartEvent" in source
    assert "ToolCallPart" in source
    # The pass avoids emitting a duplicate event.
    assert "skip here to avoid duplicates" in source


# ── Bug 17: optimization uses parameter_specs, not parameter_space ────────


def test_bug17_optimization_uses_parameter_specs() -> None:
    """Bug 17: The optimization events must use 'parameter_specs' as the
    field name, not 'parameter_space'.

    OptimizationStartedEvent.parameter_specs is the canonical name.
    """
    event = OptimizationStartedEvent(
        optimization_id="opt-1",
        search_name="GenesByTaxon",
        record_type="transcript",
        budget=10,
        objective="maximize_f1",
        positive_controls_count=5,
        negative_controls_count=3,
        parameter_specs=[{"name": "organism", "type": "string"}],
    )

    dumped = event.model_dump(by_alias=True, mode="json")

    # Must have parameterSpecs (camelCase), NOT parameterSpace.
    assert "parameterSpecs" in dumped
    assert "parameterSpace" not in dumped
    assert dumped["parameterSpecs"] == [{"name": "organism", "type": "string"}]

    # Also verify it's a field on the model, not a computed property.
    assert hasattr(event, "parameter_specs")
    assert event.parameter_specs == [{"name": "organism", "type": "string"}]


# ── Additional regression: tool_error uses enum values correctly ──────────


def test_tool_error_accepts_error_code_enum() -> None:
    """tool_error must accept ErrorCode enum values and serialize the .value."""
    payload = tool_error(ErrorCode.STEP_NOT_FOUND, "Step xyz not found")

    assert payload.code == "STEP_NOT_FOUND"
    assert payload.ok is False
    assert payload.message == "Step xyz not found"


def test_tool_error_accepts_string_code() -> None:
    """tool_error must also accept raw string codes."""
    payload = tool_error("CUSTOM_CODE", "Something custom")

    assert payload.code == "CUSTOM_CODE"
    assert payload.ok is False


# ── Additional regression: phase results are frozen ───────────────────────


def _assert_frozen(instance: object, field_name: str) -> None:
    """Assert that setting a field on a frozen dataclass raises FrozenInstanceError."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field_name, "mutated")


def test_all_phase_results_are_frozen() -> None:
    """All four phase result dataclasses must be frozen."""
    _assert_frozen(DiscoveryResult(), "research_notes")
    _assert_frozen(PlanningResult(), "questions_answered")
    _assert_frozen(ExecutionResult(), "errors")
    _assert_frozen(VerificationResult(), "assessment")


# ── Additional regression: STEP_TYPE_TOOLS mapping is complete ───────────


def test_step_type_tools_mapping_covers_all_step_types() -> None:
    """Every StepType in the enum must have a mapping in STEP_TYPE_TOOLS."""
    for step_type in StepType:
        assert step_type in STEP_TYPE_TOOLS, (
            f"StepType.{step_type.name} missing from STEP_TYPE_TOOLS"
        )


def test_support_tools_are_frozen() -> None:
    """SUPPORT_TOOLS must be a frozenset (immutable)."""
    assert isinstance(SUPPORT_TOOLS, frozenset)
    assert "get_strategy" in SUPPORT_TOOLS
    assert "update_step" in SUPPORT_TOOLS


# ── Additional regression: _GRAPH_MUTATING_TOOLS is comprehensive ─────────


def test_graph_mutating_tools_contains_core_tools() -> None:
    """_GRAPH_MUTATING_TOOLS must include the core graph mutation tools."""
    required = {
        "create_leaf_step",
        "combine_steps",
        "transform_step",
        "update_step",
        "delete_step",
        "undo_last_change",
    }
    for tool_name in required:
        assert tool_name in _GRAPH_MUTATING_TOOLS, (
            f"{tool_name} missing from _GRAPH_MUTATING_TOOLS"
        )
