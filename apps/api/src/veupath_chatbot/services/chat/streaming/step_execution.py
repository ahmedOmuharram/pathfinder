"""Per-step execution — runs individual plan steps with filtered toolsets.

Each planned step gets a scoped toolset (only the tools it needs) plus
support tools (get_strategy, update_step).  On failure, the toolset is
widened and limits are relaxed for a recovery attempt.
"""

from pydantic_ai import Agent
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, FilteredToolset
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents.execution import (
    EXECUTION_RECOVERY_LIMITS,
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.toolsets.execution import build_toolset
from veupath_chatbot.domain.strategy.plan import (
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.chat.streaming.node_streaming import (
    merge_usage,
    stream_call_tools,
    stream_model_request,
)
from veupath_chatbot.services.chat.streaming.phase_runner import (
    PhaseConfig,
    resolve_model,
)

logger = get_logger(__name__)

# Maps each plan step type to the primary tool the agent should use.
STEP_TYPE_TOOLS: dict[StepType, str] = {
    StepType.LEAF: "create_leaf_step",
    StepType.COMBINE: "combine_steps",
    StepType.TRANSFORM: "transform_step",
}

# Tools always available alongside the primary tool (read + fix).
SUPPORT_TOOLS: frozenset[str] = frozenset({"get_strategy", "update_step"})


def allowed_tools_for_step(step: PlannedStep) -> frozenset[str]:
    """Return the set of tool names allowed for a given planned step."""
    primary = STEP_TYPE_TOOLS.get(step.step_type)
    if primary is None:
        # Unknown step type — allow all tools (fall back to full toolset).
        return frozenset()
    return frozenset({primary}) | SUPPORT_TOOLS


def format_step_instruction(
    step: PlannedStep,
    input_step_ids: list[str] | None = None,
) -> str:
    """Build a concise prompt for executing one planned step."""
    parts: list[str] = [
        f"Execute planned step '{step.id}' ({step.display_name}).",
    ]

    if step.step_type == StepType.LEAF:
        params_text = ", ".join(
            f"{p.name}={p.value!r}" for p in step.parameters.values() if p.value is not None
        )
        parts.append(
            f"Create a leaf step: search_name='{step.search_name}', "
            f"record_type='{step.record_type}', parameters: {{{params_text}}}."
        )
    elif step.step_type == StepType.COMBINE:
        ids_text = f" Input step IDs: {input_step_ids}." if input_step_ids else ""
        parts.append(
            f"Combine the input steps using combine_steps with operator '{step.operator}'.{ids_text}"
        )
    elif step.step_type == StepType.TRANSFORM:
        params_text = ", ".join(
            f"{p.name}={p.value!r}" for p in step.parameters.values() if p.value is not None
        )
        parts.append(
            f"Apply transform: search_name='{step.search_name}', "
            f"parameters: {{{params_text}}}."
        )

    if step.rationale:
        parts.append(f"Rationale: {step.rationale}")

    return " ".join(parts)


async def run_step_with_agent(
    step: PlannedStep,
    config: PhaseConfig,
    allowed_tools: frozenset[str],
    usage_limits: UsageLimits,
    input_step_ids: list[str] | None = None,
) -> bool:
    """Run the execution agent for a single step with a filtered toolset.

    When *allowed_tools* is non-empty, the agent sees only those tools.
    When empty, the full execution toolset is used (recovery / unknown type).

    Returns ``True`` on success, ``False`` on failure.
    """
    full_toolset = build_toolset()
    instruction = format_step_instruction(step, input_step_ids)

    toolset_for_run: AbstractToolset[AgentDeps]
    if allowed_tools:
        def filter_func(_ctx: RunContext[AgentDeps], tool_def: ToolDefinition) -> bool:
            return tool_def.name in allowed_tools

        toolset_for_run = FilteredToolset(full_toolset, filter_func=filter_func)
    else:
        toolset_for_run = full_toolset

    resolved = resolve_model(config.model_id)

    try:
        with execution_agent.override(model=resolved, toolsets=[toolset_for_run]):
            async with execution_agent.iter(
                instruction,
                deps=config.deps,
                usage_limits=usage_limits,
            ) as run:
                async for node in run:
                    if Agent.is_model_request_node(node):
                        await stream_model_request(
                            node, run, config.queue, config.message_id, config.counters
                        )
                    elif Agent.is_call_tools_node(node):
                        await stream_call_tools(node, run, config.queue, config.deps, config.counters)

                merge_usage(config.counters, run.usage())
                return True
    except Exception:
        logger.exception("Step execution failed", step_id=step.id)
        return False


async def run_execution_phase(config: PhaseConfig) -> None:
    """Run the execution phase with per-step toolset filtering and usage limits.

    Instead of giving the LLM the full toolset for the entire execution,
    this iterates through the plan's steps in dependency order.  Each step
    gets a FilteredToolset exposing only the relevant tool(s) plus read/fix
    support tools.  On failure, the toolset is widened and limits are relaxed
    for a recovery attempt.
    """
    active_plan = config.deps.agent_state.active_plan
    if active_plan is None:
        logger.warning("Execution phase entered without an active plan")
        return

    active_plan.status = PlanStatus.EXECUTING

    try:
        ordered_steps = active_plan.steps_in_dependency_order()
    except ValueError:
        logger.exception("Plan has cyclic dependencies — falling back to list order")
        ordered_steps = list(active_plan.steps)

    # Build a map of step_id → input step IDs from plan connections.
    step_inputs: dict[str, list[str]] = {}
    for conn in active_plan.connections:
        step_inputs.setdefault(conn.to_step, []).append(conn.from_step)

    for step in ordered_steps:
        step.status = StepStatus.EXECUTING
        allowed = allowed_tools_for_step(step)
        inputs = step_inputs.get(step.id)

        try:
            if allowed:
                success = await run_step_with_agent(
                    step, config, allowed, EXECUTION_USAGE_LIMITS, inputs,
                )
            else:
                success = await run_step_with_agent(
                    step, config, frozenset(), EXECUTION_USAGE_LIMITS, inputs,
                )

            if not success and allowed:
                logger.info(
                    "Step failed, attempting recovery with full toolset",
                    step_id=step.id,
                    step_type=step.step_type,
                )
                success = await run_step_with_agent(
                    step, config, frozenset(), EXECUTION_RECOVERY_LIMITS, inputs,
                )
        except Exception:
            logger.exception("Step execution raised an exception", step_id=step.id)
            success = False

        step.status = StepStatus.COMPLETE if success else StepStatus.FAILED
        if not success:
            logger.warning("Step execution failed", step_id=step.id)

    # Update plan status based on step outcomes.
    all_complete = all(
        s.status == StepStatus.COMPLETE for s in active_plan.steps
    )
    active_plan.status = PlanStatus.COMPLETE if all_complete else PlanStatus.FAILED
