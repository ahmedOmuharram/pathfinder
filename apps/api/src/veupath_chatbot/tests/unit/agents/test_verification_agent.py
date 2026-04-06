"""Behavioral tests for the verification agent using FunctionModel.

Tests verify:
- Agent configuration (name, tool count, model, usage limits, deferred check)
- FunctionModel-scripted behavioral test: agent calls get_strategy
- Tool visibility: all 18 verification tools visible to FunctionModel
- Dynamic instructions: 3 instruction functions registered on the agent
"""

import asyncio

import pytest
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents.state import AgentToolState
from veupath_chatbot.ai.agents.verification import (
    VERIFICATION_USAGE_LIMITS,
    verification_agent,
)
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategySession

# ---------------------------------------------------------------------------
# Expected tool names (alphabetical, from the verification toolset)
# ---------------------------------------------------------------------------

EXPECTED_TOOLS: frozenset[str] = frozenset(
    {
        "create_workbench_gene_set",
        "export_gene_set",
        "get_confidence_scores",
        "get_download_url",
        "get_enrichment_results",
        "get_ensemble_analysis",
        "get_estimated_size",
        "get_evaluation_summary",
        "get_experiment_config",
        "get_result_gene_lists",
        "get_sample_records",
        "get_step_contributions",
        "get_strategy",
        "list_workbench_gene_sets",
        "optimize_search_parameters",
        "run_control_tests_on_search",
        "run_control_tests_on_step",
        "run_gene_set_enrichment",
    }
)

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


# ===========================================================================
# Test 1: Agent configuration
# ===========================================================================


class TestVerificationAgentConfiguration:
    """Verify verification agent static configuration."""

    def test_agent_name(self) -> None:
        assert verification_agent.name == "verification"

    def test_tool_count(self) -> None:
        """Verification agent has 18 tools."""
        toolset = verification_agent._user_toolsets[0]
        assert isinstance(toolset, FunctionToolset)
        assert len(toolset.tools) == 18

    def test_defers_model_check(self) -> None:
        """defer_model_check=True means the model is stored as a raw string."""
        assert isinstance(verification_agent._model, str)
        assert verification_agent._model == "anthropic:claude-sonnet-4-5"

    def test_usage_limits_request(self) -> None:
        assert VERIFICATION_USAGE_LIMITS.request_limit == 15

    def test_usage_limits_tokens(self) -> None:
        assert VERIFICATION_USAGE_LIMITS.total_tokens_limit == 40_000

    def test_tool_names_match_expected(self) -> None:
        """All 18 expected tool names are registered in the toolset."""
        toolset = verification_agent._user_toolsets[0]
        assert isinstance(toolset, FunctionToolset)
        registered = frozenset(toolset.tools.keys())
        assert registered == EXPECTED_TOOLS


# ===========================================================================
# Test 2: FunctionModel behavioral test -- agent calls get_strategy
# ===========================================================================


class TestVerificationAgentFunctionModel:
    """Use FunctionModel to script the verification agent making tool calls.

    Scripts the agent to call get_strategy (a lightweight, no-network tool)
    to verify the FunctionModel -> tool call -> result -> text response cycle.
    """

    @pytest.mark.anyio
    async def test_agent_calls_get_strategy_via_function_model(self) -> None:
        """FunctionModel drives the agent to call get_strategy and produce text."""
        deps = _make_deps()

        # Create a graph with a step so get_strategy returns meaningful data
        graph = deps.strategy_session.create_graph("Verification Test Strategy")
        step = PlanStepNode(
            search_name="GenesByTaxon",
            display_name="P. falciparum genes",
            parameters={"organism": "Plasmodium falciparum 3D7"},
        )
        graph.add_step(step)
        graph.step_counts[step.id] = 3217

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
                            tool_call_id="call_verify_1",
                        )
                    ]
                )

            # Second call: final text response referencing data from the tool
            return ModelResponse(
                parts=[
                    TextPart(
                        content=(
                            "Strategy has 1 step (GenesByTaxon) with 3217 results. "
                            "Verification complete."
                        )
                    )
                ]
            )

        with capture_run_messages() as messages:
            result = await verification_agent.run(
                "Verify the current strategy before reporting results.",
                deps=deps,
                model=FunctionModel(scripted_model),
                usage_limits=UsageLimits(request_limit=5),
            )

        # Verify the agent produced a string result
        assert isinstance(result.output, str)
        assert "3217" in result.output

        # Verify the model was called exactly twice (tool call + text response)
        assert call_count == 2

        # Verify get_strategy tool call appears in captured messages
        all_messages = messages[:]
        tool_call_found = False
        for msg in all_messages:
            if not hasattr(msg, "parts"):
                continue
            for part in msg.parts:
                if hasattr(part, "tool_name") and part.tool_name == "get_strategy":
                    tool_call_found = True
        assert tool_call_found, "Expected get_strategy tool call in captured messages"

    @pytest.mark.anyio
    async def test_agent_tool_result_flows_to_response(self) -> None:
        """Verify the tool result is available in messages when the model responds."""
        deps = _make_deps()

        graph = deps.strategy_session.create_graph("Flow Test")
        step = PlanStepNode(
            search_name="GenesByGoTerm",
            display_name="GO term genes",
            parameters={"GoTerm": "GO:0005515"},
        )
        graph.add_step(step)
        graph.step_counts[step.id] = 891

        call_count = 0

        def scripted_model(
            messages: list[object], info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name="get_strategy",
                            args={"summary_only": True},
                            tool_call_id="call_flow_1",
                        )
                    ]
                )

            # Second call: the model now has access to the tool result in messages
            return ModelResponse(
                parts=[TextPart(content="Verified: 1 step, gene count looks reasonable.")]
            )

        with capture_run_messages() as messages:
            result = await verification_agent.run(
                "Check the strategy.",
                deps=deps,
                model=FunctionModel(scripted_model),
                usage_limits=UsageLimits(request_limit=5),
            )

        assert isinstance(result.output, str)
        assert call_count == 2

        # Verify the tool return part appears in captured messages
        tool_return_found = False
        for msg in messages[:]:
            if not hasattr(msg, "parts"):
                continue
            for part in msg.parts:
                if (
                    hasattr(part, "tool_name")
                    and hasattr(part, "content")
                    and part.tool_name == "get_strategy"
                ):
                    tool_return_found = True
        assert tool_return_found, "Expected get_strategy tool return in captured messages"


# ===========================================================================
# Test 3: Tool visibility via FunctionModel introspection
# ===========================================================================


class TestVerificationToolVisibility:
    """Use FunctionModel to introspect AgentInfo.function_tools and verify
    all 18 verification tools are visible to the model.
    """

    @pytest.mark.anyio
    async def test_all_18_tools_visible_to_function_model(self) -> None:
        """Verify the FunctionModel receives all 18 tool definitions."""
        deps = _make_deps()
        deps.strategy_session.create_graph("Visibility Test")

        captured_tool_names: list[str] = []

        def introspecting_model(
            messages: list[object], info: AgentInfo
        ) -> ModelResponse:
            if info.function_tools:
                captured_tool_names.extend(t.name for t in info.function_tools)
            return ModelResponse(parts=[TextPart(content="Done.")])

        await verification_agent.run(
            "Check strategy.",
            deps=deps,
            model=FunctionModel(introspecting_model),
            usage_limits=UsageLimits(request_limit=2),
        )

        assert len(captured_tool_names) == 18
        assert frozenset(captured_tool_names) == EXPECTED_TOOLS

    @pytest.mark.anyio
    async def test_individual_tool_categories_present(self) -> None:
        """Verify tools from each category (results, export, workbench, etc.) are present."""
        deps = _make_deps()
        deps.strategy_session.create_graph("Category Test")

        captured_tool_names: set[str] = set()

        def introspecting_model(
            messages: list[object], info: AgentInfo
        ) -> ModelResponse:
            if info.function_tools:
                captured_tool_names.update(t.name for t in info.function_tools)
            return ModelResponse(parts=[TextPart(content="Done.")])

        await verification_agent.run(
            "Check.",
            deps=deps,
            model=FunctionModel(introspecting_model),
            usage_limits=UsageLimits(request_limit=2),
        )

        # Results inspection tools
        assert "get_estimated_size" in captured_tool_names
        assert "get_sample_records" in captured_tool_names
        assert "get_download_url" in captured_tool_names

        # Control test tools
        assert "run_control_tests_on_step" in captured_tool_names
        assert "run_control_tests_on_search" in captured_tool_names

        # Optimization tool
        assert "optimize_search_parameters" in captured_tool_names

        # Workbench tools
        assert "create_workbench_gene_set" in captured_tool_names
        assert "run_gene_set_enrichment" in captured_tool_names
        assert "list_workbench_gene_sets" in captured_tool_names

        # Export tool
        assert "export_gene_set" in captured_tool_names

        # Workbench read tools
        assert "get_evaluation_summary" in captured_tool_names
        assert "get_enrichment_results" in captured_tool_names
        assert "get_confidence_scores" in captured_tool_names
        assert "get_step_contributions" in captured_tool_names
        assert "get_experiment_config" in captured_tool_names
        assert "get_ensemble_analysis" in captured_tool_names
        assert "get_result_gene_lists" in captured_tool_names

        # Strategy graph tool
        assert "get_strategy" in captured_tool_names


# ===========================================================================
# Test 4: Dynamic instructions registration
# ===========================================================================


class TestVerificationDynamicInstructions:
    """Verify the 3 dynamic instruction functions are registered on the agent."""

    def test_five_instruction_entries_registered(self) -> None:
        """The agent has 4 instruction entries: 1 static string + 3 dynamic callables."""
        instructions = verification_agent._instructions
        assert len(instructions) == 5

    def test_static_instruction_is_string(self) -> None:
        """First instruction entry is the static instruction string."""
        first = verification_agent._instructions[0]
        assert isinstance(first, str)
        assert "Verification Agent" in first

    def test_pinned_context_summary_registered(self) -> None:
        """_pinned_context_summary is registered as a dynamic instruction."""
        callables = [
            fn for fn in verification_agent._instructions if callable(fn)
        ]
        names = [fn.__name__ for fn in callables]
        assert "_pinned_context_summary" in names

    def test_pinned_graph_state_registered(self) -> None:
        """_pinned_graph_state is registered as a dynamic instruction."""
        callables = [
            fn for fn in verification_agent._instructions if callable(fn)
        ]
        names = [fn.__name__ for fn in callables]
        assert "_pinned_graph_state" in names

    def test_mentioned_context_registered(self) -> None:
        """_mentioned_context is registered as a dynamic instruction."""
        callables = [
            fn for fn in verification_agent._instructions if callable(fn)
        ]
        names = [fn.__name__ for fn in callables]
        assert "_mentioned_context" in names

    def test_all_four_dynamic_functions_present(self) -> None:
        """All 3 dynamic instruction functions are registered (no more, no fewer)."""
        callables = [
            fn for fn in verification_agent._instructions if callable(fn)
        ]
        assert len(callables) == 4
        names = frozenset(fn.__name__ for fn in callables)
        assert names == frozenset(
            {"_base_system_prompt", "_pinned_context_summary", "_pinned_graph_state", "_mentioned_context"}
        )
