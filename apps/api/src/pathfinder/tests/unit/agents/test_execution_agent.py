"""Behavioral tests for the execution agent's plan-guided execution pattern.

Tests verify:
- Tool filtering per step type (LEAF, COMBINE, TRANSFORM)
- Step instruction formatting for each step type
- Dependency ordering via topological sort
- Execution agent configuration (tool count, name, usage limits)
- FunctionModel-scripted behavioral test: agent makes tool calls
"""

import asyncio

import pytest
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.execution import (
    EXECUTION_RECOVERY_LIMITS,
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.chat.streaming.step_execution import (
    allowed_tools_for_step,
    format_step_instruction,
)
from pathfinder.services.strategies.sync_state import WDKSyncState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    session = StrategySession(site_id=site_id)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
        event_queue=asyncio.Queue(),
    )


def _make_leaf_step(
    step_id: str = "step_a",
    search_name: str = "GenesByTaxon",
    display_name: str = "Taxon genes",
) -> PlannedStep:
    return PlannedStep(
        id=step_id,
        search_name=search_name,
        display_name=display_name,
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters={
            "organism": PlannedParameter(
                name="organism",
                display_name="Organism",
                param_type="string",
                value='["Plasmodium falciparum 3D7"]',
                status=ParamStatus.SET,
                required=True,
            ),
        },
    )


def _make_combine_step(
    step_id: str = "step_c",
    operator: str = "INTERSECT",
) -> PlannedStep:
    return PlannedStep(
        id=step_id,
        search_name="",
        display_name="Combined",
        step_type=StepType.COMBINE,
        status=StepStatus.READY,
        operator=operator,
    )


def _make_transform_step(
    step_id: str = "step_t",
    search_name: str = "GenesByOrthologPattern",
) -> PlannedStep:
    return PlannedStep(
        id=step_id,
        search_name=search_name,
        display_name="Ortholog transform",
        step_type=StepType.TRANSFORM,
        status=StepStatus.READY,
        parameters={
            "phyletic_pattern": PlannedParameter(
                name="phyletic_pattern",
                display_name="Phyletic Pattern",
                param_type="string",
                value="pfal+",
                status=ParamStatus.SET,
                required=True,
            ),
        },
    )


def _make_multi_step_plan() -> StrategyPlan:
    """Build a plan with 2 leaves + 1 combine step connected."""
    leaf_a = _make_leaf_step(step_id="step_a")
    leaf_b = PlannedStep(
        id="step_b",
        search_name="GenesByGoTerm",
        display_name="GO genes",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters={
            "GoTerm": PlannedParameter(
                name="GoTerm",
                display_name="GO Term",
                param_type="string",
                value="GO:0005515",
                status=ParamStatus.SET,
                required=True,
            ),
        },
    )
    combine = _make_combine_step(step_id="step_c")
    return StrategyPlan(
        title="Test plan",
        description="Test",
        rationale="Test",
        status=PlanStatus.APPROVED,
        steps=[leaf_a, leaf_b, combine],
        connections=[
            PlannedConnection(from_step="step_a", to_step="step_c"),
            PlannedConnection(from_step="step_b", to_step="step_c"),
        ],
    )


# ===========================================================================
# Test 1: Tool filtering per step type
# ===========================================================================


class TestAllowedToolsForStep:
    """Verify allowed_tools_for_step returns the correct tool set per step type."""

    def test_leaf_step_gets_create_leaf_step_tool(self) -> None:
        step = _make_leaf_step()
        allowed = allowed_tools_for_step(step)
        assert "create_leaf_step" in allowed
        assert "get_strategy" in allowed
        assert "update_step" in allowed
        assert len(allowed) == 3

    def test_combine_step_gets_combine_steps_tool(self) -> None:
        step = _make_combine_step()
        allowed = allowed_tools_for_step(step)
        assert "combine_steps" in allowed
        assert "get_strategy" in allowed
        assert "update_step" in allowed
        assert len(allowed) == 3

    def test_transform_step_gets_transform_step_tool(self) -> None:
        step = _make_transform_step()
        allowed = allowed_tools_for_step(step)
        assert "transform_step" in allowed
        assert "get_strategy" in allowed
        assert "update_step" in allowed
        assert len(allowed) == 3

    def test_support_tools_always_present(self) -> None:
        """get_strategy and update_step are included for all known step types."""
        for factory in [_make_leaf_step, _make_combine_step, _make_transform_step]:
            step = factory()
            allowed = allowed_tools_for_step(step)
            assert "get_strategy" in allowed
            assert "update_step" in allowed

    def test_each_step_type_gets_different_primary_tool(self) -> None:
        """Each step type maps to a distinct primary tool."""
        leaf_tools = allowed_tools_for_step(_make_leaf_step())
        combine_tools = allowed_tools_for_step(_make_combine_step())
        transform_tools = allowed_tools_for_step(_make_transform_step())

        # Primary tools are mutually exclusive
        leaf_primary = leaf_tools - frozenset({"get_strategy", "update_step"})
        combine_primary = combine_tools - frozenset({"get_strategy", "update_step"})
        transform_primary = transform_tools - frozenset({"get_strategy", "update_step"})

        assert leaf_primary == {"create_leaf_step"}
        assert combine_primary == {"combine_steps"}
        assert transform_primary == {"transform_step"}
        assert leaf_primary.isdisjoint(combine_primary)
        assert leaf_primary.isdisjoint(transform_primary)
        assert combine_primary.isdisjoint(transform_primary)

    def test_returns_frozenset(self) -> None:
        """Return type is frozenset (immutable)."""
        allowed = allowed_tools_for_step(_make_leaf_step())
        assert type(allowed) is frozenset


# ===========================================================================
# Test 2: Step instruction formatting
# ===========================================================================


class TestFormatStepInstruction:
    """Verify format_step_instruction generates correct prompts."""

    def test_leaf_instruction_includes_search_name_and_parameters(self) -> None:
        step = _make_leaf_step()
        instruction = format_step_instruction(step)
        assert "step_a" in instruction
        assert "Taxon genes" in instruction
        assert "GenesByTaxon" in instruction
        assert "organism" in instruction
        assert "Plasmodium falciparum 3D7" in instruction
        assert "Create a leaf step" in instruction

    def test_combine_instruction_includes_operator(self) -> None:
        step = _make_combine_step(operator="INTERSECT")
        instruction = format_step_instruction(step)
        assert "step_c" in instruction
        assert "Combined" in instruction
        assert "INTERSECT" in instruction
        assert "Combine the input steps" in instruction
        assert "combine_steps" in instruction

    def test_transform_instruction_includes_search_name_and_parameters(self) -> None:
        step = _make_transform_step()
        instruction = format_step_instruction(step)
        assert "step_t" in instruction
        assert "Ortholog transform" in instruction
        assert "GenesByOrthologPattern" in instruction
        assert "phyletic_pattern" in instruction
        assert "pfal+" in instruction
        assert "Apply transform" in instruction

    def test_leaf_instruction_includes_record_type(self) -> None:
        step = _make_leaf_step()
        instruction = format_step_instruction(step)
        assert "record_type='transcript'" in instruction

    def test_rationale_included_when_present(self) -> None:
        step = _make_leaf_step()
        step.rationale = "Most direct search for organism filtering"
        instruction = format_step_instruction(step)
        assert "Rationale: Most direct search for organism filtering" in instruction

    def test_rationale_omitted_when_empty(self) -> None:
        step = _make_leaf_step()
        step.rationale = ""
        instruction = format_step_instruction(step)
        assert "Rationale" not in instruction

    def test_parameters_with_none_values_excluded(self) -> None:
        """Parameters with value=None are not included in the instruction."""
        step = PlannedStep(
            id="step_x",
            search_name="GenesByTaxon",
            display_name="Taxon genes",
            step_type=StepType.LEAF,
            status=StepStatus.READY,
            parameters={
                "organism": PlannedParameter(
                    name="organism",
                    display_name="Organism",
                    param_type="string",
                    value='["Plasmodium falciparum 3D7"]',
                    status=ParamStatus.SET,
                    required=True,
                ),
                "optional_param": PlannedParameter(
                    name="optional_param",
                    display_name="Optional",
                    param_type="string",
                    value=None,
                    status=ParamStatus.DEFAULT,
                    required=False,
                ),
            },
        )
        instruction = format_step_instruction(step)
        assert "organism=" in instruction
        assert "optional_param" not in instruction


# ===========================================================================
# Test 3: Dependency ordering
# ===========================================================================


class TestDependencyOrdering:
    """Verify plan.steps_in_dependency_order() returns leaves before combine."""

    def test_leaves_before_combine(self) -> None:
        plan = _make_multi_step_plan()
        ordered = plan.steps_in_dependency_order()
        step_ids = [s.id for s in ordered]

        assert step_ids.index("step_a") < step_ids.index("step_c")
        assert step_ids.index("step_b") < step_ids.index("step_c")

    def test_all_steps_present(self) -> None:
        plan = _make_multi_step_plan()
        ordered = plan.steps_in_dependency_order()
        assert len(ordered) == 3
        ordered_ids = {s.id for s in ordered}
        assert ordered_ids == {"step_a", "step_b", "step_c"}

    def test_single_leaf_trivial_ordering(self) -> None:
        plan = StrategyPlan(
            title="Single leaf",
            description="Single leaf plan",
            rationale="Test",
            status=PlanStatus.APPROVED,
            steps=[_make_leaf_step()],
            connections=[],
        )
        ordered = plan.steps_in_dependency_order()
        assert len(ordered) == 1
        assert ordered[0].id == "step_a"

    def test_cycle_detection_raises_value_error(self) -> None:
        """Cyclic dependencies raise ValueError."""
        plan = StrategyPlan(
            title="Cyclic",
            description="Cyclic plan",
            rationale="Test",
            status=PlanStatus.APPROVED,
            steps=[
                _make_leaf_step(step_id="x"),
                _make_leaf_step(step_id="y"),
            ],
            connections=[
                PlannedConnection(from_step="x", to_step="y"),
                PlannedConnection(from_step="y", to_step="x"),
            ],
        )
        with pytest.raises(ValueError, match="Cycle detected"):
            plan.steps_in_dependency_order()

    def test_chain_of_three_preserves_order(self) -> None:
        """leaf -> transform -> combine: all in correct order."""
        leaf = _make_leaf_step(step_id="s1")
        transform = _make_transform_step(step_id="s2")
        combine = _make_combine_step(step_id="s3")
        plan = StrategyPlan(
            title="Chain",
            description="Chain plan",
            rationale="Test",
            status=PlanStatus.APPROVED,
            steps=[combine, transform, leaf],  # intentionally shuffled
            connections=[
                PlannedConnection(from_step="s1", to_step="s2"),
                PlannedConnection(from_step="s2", to_step="s3"),
            ],
        )
        ordered = plan.steps_in_dependency_order()
        step_ids = [s.id for s in ordered]
        assert step_ids == ["s1", "s2", "s3"]


# ===========================================================================
# Test 4: Execution agent configuration
# ===========================================================================


class TestExecutionAgentConfiguration:
    """Verify execution agent static configuration."""

    def test_agent_name(self) -> None:
        assert execution_agent.name == "execution"

    def test_tool_count(self) -> None:
        """Execution agent has 13 tools."""
        toolset = execution_agent._user_toolsets[0]
        assert isinstance(toolset, FunctionToolset)
        assert len(toolset.tools) == 13

    def test_usage_limits(self) -> None:
        assert EXECUTION_USAGE_LIMITS.request_limit == 3
        assert EXECUTION_USAGE_LIMITS.total_tokens_limit == 30_000

    def test_recovery_limits_higher_than_standard(self) -> None:
        recovery_req = EXECUTION_RECOVERY_LIMITS.request_limit
        standard_req = EXECUTION_USAGE_LIMITS.request_limit
        assert recovery_req is not None
        assert standard_req is not None
        assert recovery_req > standard_req

        recovery_tok = EXECUTION_RECOVERY_LIMITS.total_tokens_limit
        standard_tok = EXECUTION_USAGE_LIMITS.total_tokens_limit
        assert recovery_tok is not None
        assert standard_tok is not None
        assert recovery_tok > standard_tok

    def test_defers_model_check(self) -> None:
        assert isinstance(execution_agent._model, str)
        assert execution_agent._model == "anthropic:claude-sonnet-4-5"


# ===========================================================================
# Test 5: FunctionModel behavioral test — agent calls get_strategy
# ===========================================================================


class TestExecutionAgentFunctionModel:
    """Use FunctionModel to script the execution agent making a tool call.

    Scripts the agent to call get_strategy (a lightweight, no-network tool)
    to verify the FunctionModel -> tool call -> result -> text response cycle.
    """

    @pytest.mark.asyncio
    async def test_agent_calls_get_strategy_via_function_model(self) -> None:
        """FunctionModel drives the agent to call get_strategy and produce text."""
        deps = _make_deps()

        # Create a graph with a step so get_strategy returns meaningful data
        graph = deps.strategy_session.create_graph("Test Strategy")
        sync_state = WDKSyncState()
        deps.strategy_session.sync_state = sync_state
        step = PlanStepNode(
            search_name="GenesByTaxon",
            display_name="Taxon genes",
            parameters={"organism": "Plasmodium falciparum 3D7"},
        )
        graph.add_step(step)
        sync_state.step_counts[step.id] = 5432

        call_count = 0

        def scripted_model(
            messages: list[object], info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: invoke get_strategy to read the graph
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name="get_strategy",
                            args={"summary_only": True},
                            tool_call_id="call_get_1",
                        )
                    ]
                )

            # Second call: final text response
            return ModelResponse(
                parts=[TextPart(content="Strategy has 1 step (GenesByTaxon) with 5432 results.")]
            )

        with capture_run_messages() as messages:
            result = await execution_agent.run(
                "Check the current strategy state before proceeding.",
                deps=deps,
                model=FunctionModel(scripted_model),
                usage_limits=UsageLimits(request_limit=5),
            )

        # Verify the agent produced a string result
        assert isinstance(result.output, str)
        assert "5432" in result.output

        # Verify the model was called exactly twice (tool call + text response)
        assert call_count == 2

        # Verify get_strategy tool call appears in captured messages
        all_messages = messages[:]
        tool_call_found = False
        for msg in all_messages:
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if hasattr(part, "tool_name") and part.tool_name == "get_strategy":
                        tool_call_found = True
        assert tool_call_found, "Expected get_strategy tool call in captured messages"

    @pytest.mark.asyncio
    async def test_agent_tool_names_visible_to_function_model(self) -> None:
        """Verify the FunctionModel receives tool definitions from the execution toolset."""
        deps = _make_deps()
        deps.strategy_session.create_graph("Test Strategy")

        captured_tool_names: list[str] = []

        def introspecting_model(
            messages: list[object], info: AgentInfo
        ) -> ModelResponse:
            # Capture the tool names the agent exposes to the model
            if info.function_tools:
                captured_tool_names.extend(t.name for t in info.function_tools)
            return ModelResponse(
                parts=[TextPart(content="Done.")]
            )

        await execution_agent.run(
            "Check strategy.",
            deps=deps,
            model=FunctionModel(introspecting_model),
            usage_limits=UsageLimits(request_limit=2),
        )

        # Verify all 12 execution tools are visible to the model
        assert len(captured_tool_names) == 13
        assert "create_leaf_step" in captured_tool_names
        assert "combine_steps" in captured_tool_names
        assert "transform_step" in captured_tool_names
        assert "get_strategy" in captured_tool_names
        assert "update_step" in captured_tool_names
        assert "delete_step" in captured_tool_names
        assert "rename_strategy" in captured_tool_names
