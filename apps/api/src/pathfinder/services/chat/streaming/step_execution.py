"""Per-step execution — runs individual plan steps with filtered toolsets.

Each planned step gets a scoped toolset (only the tools it needs) plus
support tools (get_strategy, update_step).  On failure, the toolset is
widened and limits are relaxed for a recovery attempt.
"""

from datetime import UTC, datetime
from typing import Final

from pydantic_ai import Agent
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, FilteredToolset
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.execution import (
    EXECUTION_RECOVERY_LIMITS,
    EXECUTION_USAGE_LIMITS,
    execution_agent,
)
from pathfinder.ai.models.settings import build_model_settings
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.toolsets.execution import build_toolset
from pathfinder.domain.strategy.plan import (
    PlannedConnection,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.platform.event_schemas_pipeline import PlanUpdatedEventData
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.node_streaming import (
    StreamMessageContext,
    merge_usage,
    stream_call_tools,
    stream_model_request,
)
from pathfinder.services.chat.streaming.phase_runner import (
    PhaseConfig,
    resolve_model,
)

logger = get_logger(__name__)

_PRIMARY_INPUT_ORDER: Final[dict[str, int]] = {
    "primary": 0,
    "secondary": 1,
}
_COMBINE_INPUT_COUNT: Final[int] = 2
_TRANSFORM_INPUT_COUNT: Final[int] = 1

# Maps each plan step type to the primary tool the agent should use.
STEP_TYPE_TOOLS: dict[StepType, str] = {
    StepType.LEAF: "create_leaf_step",
    StepType.COMBINE: "combine_steps",
    StepType.TRANSFORM: "transform_step",
}

# Tools always available alongside the primary tool (read + fix).
SUPPORT_TOOLS: frozenset[str] = frozenset({"get_strategy", "update_step"})


class StepExecutionResolutionError(RuntimeError):
    """Raised when a planned execution step cannot be mapped safely."""


async def emit_plan_update(
    config: PhaseConfig,
    plan: StrategyPlan,
) -> None:
    """Emit a full plan snapshot update for authoritative UI sync."""
    plan.updated_at = datetime.now(UTC)
    updates: JSONObject = plan.model_dump(by_alias=True, mode="json")
    await config.queue.put(
        {
            "type": "plan_updated",
            "data": PlanUpdatedEventData(
                plan_id=plan.id,
                updates=updates,
            ).model_dump(by_alias=True),
        }
    )


def allowed_tools_for_step(step: PlannedStep) -> frozenset[str]:
    """Return the set of tool names allowed for a given planned step."""
    primary = STEP_TYPE_TOOLS.get(step.step_type)
    if primary is None:
        # Unknown step type — allow all tools (fall back to full toolset).
        return frozenset()
    return frozenset({primary}) | SUPPORT_TOOLS


def _sorted_connections(
    connections: list[PlannedConnection],
) -> list[PlannedConnection]:
    """Return connections in deterministic primary/secondary order."""
    return sorted(
        connections,
        key=lambda conn: (
            _PRIMARY_INPUT_ORDER.get(conn.input_type.lower(), 2),
            conn.from_step,
        ),
    )


def _build_incoming_connection_index(
    plan: StrategyPlan,
) -> dict[str, list[PlannedConnection]]:
    """Index plan connections by downstream step ID."""
    incoming: dict[str, list[PlannedConnection]] = {}
    for connection in plan.connections:
        incoming.setdefault(connection.to_step, []).append(connection)
    return incoming


def _validate_input_arity(step: PlannedStep, input_step_ids: list[str]) -> None:
    """Validate the number of resolved inputs for a planned step."""
    if (
        step.step_type == StepType.COMBINE
        and len(input_step_ids) != _COMBINE_INPUT_COUNT
    ):
        msg = (
            f"Planned combine step '{step.id}' requires {_COMBINE_INPUT_COUNT} "
            f"mapped input steps, "
            f"but resolved {len(input_step_ids)}."
        )
        raise StepExecutionResolutionError(msg)
    if (
        step.step_type == StepType.TRANSFORM
        and len(input_step_ids) != _TRANSFORM_INPUT_COUNT
    ):
        msg = (
            f"Planned transform step '{step.id}' requires {_TRANSFORM_INPUT_COUNT} "
            f"mapped input step, "
            f"but resolved {len(input_step_ids)}."
        )
        raise StepExecutionResolutionError(msg)


def resolve_input_step_ids(
    plan: StrategyPlan,
    step: PlannedStep,
    *,
    active_graph_step_ids: set[str],
    active_root_ids: set[str],
    incoming_connections: dict[str, list[PlannedConnection]],
) -> list[str] | None:
    """Resolve planned dependency edges to authoritative graph step IDs."""
    connections = _sorted_connections(incoming_connections.get(step.id, []))
    if not connections:
        return None

    step_by_id = {planned_step.id: planned_step for planned_step in plan.steps}
    resolved_inputs: list[str] = []
    for connection in connections:
        upstream = step_by_id.get(connection.from_step)
        if upstream is None:
            msg = (
                f"Planned step '{step.id}' depends on unknown step "
                f"'{connection.from_step}'."
            )
            raise StepExecutionResolutionError(msg)
        if upstream.graph_step_id is None:
            msg = (
                f"Planned dependency '{connection.from_step}' for step '{step.id}' "
                "has no resolved graph step ID yet."
            )
            raise StepExecutionResolutionError(msg)
        if upstream.graph_step_id not in active_graph_step_ids:
            msg = (
                f"Resolved graph step '{upstream.graph_step_id}' for planned step "
                f"'{connection.from_step}' is missing from the active strategy graph."
            )
            raise StepExecutionResolutionError(msg)
        if upstream.graph_step_id not in active_root_ids:
            msg = (
                f"Resolved graph step '{upstream.graph_step_id}' for planned step "
                f"'{connection.from_step}' is no longer a root, so reusing it would "
                "silently duplicate the subtree."
            )
            raise StepExecutionResolutionError(msg)
        resolved_inputs.append(upstream.graph_step_id)

    _validate_input_arity(step, resolved_inputs)
    return resolved_inputs


def _capture_graph_state(config: PhaseConfig) -> tuple[set[str], set[str]]:
    """Capture the active graph's step IDs and roots before a step runs."""
    graph = config.deps.strategy_session.get_graph(None)
    if graph is None:
        return set(), set()
    return set(graph.steps), set(graph.roots)


def _record_step_mapping(
    step: PlannedStep,
    config: PhaseConfig,
    *,
    prior_step_ids: set[str],
    prior_roots: set[str],
) -> None:
    """Persist the real graph/WDK IDs produced for one planned step."""
    graph = config.deps.strategy_session.get_graph(None)
    if graph is None:
        msg = f"Execution for planned step '{step.id}' did not leave an active graph."
        raise StepExecutionResolutionError(msg)

    current_step_ids = set(graph.steps)
    new_step_ids = current_step_ids - prior_step_ids
    resolved_graph_step_id: str | None = None

    if len(new_step_ids) == 1:
        resolved_graph_step_id = next(iter(new_step_ids))
    elif len(new_step_ids) > 1:
        created = sorted(new_step_ids)
        msg = (
            f"Execution for planned step '{step.id}' created multiple graph steps "
            f"{created}. Refusing to guess which one is authoritative."
        )
        raise StepExecutionResolutionError(msg)
    elif step.graph_step_id is not None and step.graph_step_id in graph.steps:
        resolved_graph_step_id = step.graph_step_id

    if resolved_graph_step_id is None:
        msg = (
            f"Execution for planned step '{step.id}' did not produce a new graph "
            "step mapping."
        )
        raise StepExecutionResolutionError(msg)

    if resolved_graph_step_id not in graph.roots:
        msg = (
            f"Resolved graph step '{resolved_graph_step_id}' for planned step "
            f"'{step.id}' is not a current root."
        )
        raise StepExecutionResolutionError(msg)

    new_roots = graph.roots - prior_roots
    unexpected_new_roots = new_roots - {resolved_graph_step_id}
    if unexpected_new_roots:
        msg = (
            f"Execution for planned step '{step.id}' left extra disconnected roots "
            f"{sorted(unexpected_new_roots)}."
        )
        raise StepExecutionResolutionError(msg)

    sync_state = config.deps.strategy_session.sync_state
    step.graph_step_id = resolved_graph_step_id
    step.wdk_step_id = (
        sync_state.wdk_step_ids.get(resolved_graph_step_id)
        if sync_state is not None
        else None
    )
    step.actual_count = (
        sync_state.step_counts.get(resolved_graph_step_id)
        if sync_state is not None
        else None
    )
    step.failure_reason = None


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
            "Create exactly one new leaf step by calling "
            f"create_leaf_step(search_name={step.search_name!r}, "
            f"parameters={{{params_text}}}, display_name={step.display_name!r}, "
            f"record_type={step.record_type!r})."
        )
    elif step.step_type == StepType.COMBINE:
        if input_step_ids and len(input_step_ids) == _COMBINE_INPUT_COUNT:
            parts.append(
                "Create exactly one combine step by calling "
                f"combine_steps(step_a_id={input_step_ids[0]!r}, "
                f"step_b_id={input_step_ids[1]!r}, operator={step.operator!r}, "
                f"display_name={step.display_name!r})."
            )
        else:
            parts.append(
                f"Create exactly one combine step with operator {step.operator!r}."
            )
    elif step.step_type == StepType.TRANSFORM:
        params_text = ", ".join(
            f"{p.name}={p.value!r}" for p in step.parameters.values() if p.value is not None
        )
        if input_step_ids and len(input_step_ids) == _TRANSFORM_INPUT_COUNT:
            parts.append(
                "Create exactly one transform step by calling "
                f"transform_step(input_step_id={input_step_ids[0]!r}, "
                f"transform_name={step.search_name!r}, parameters={{{params_text}}}, "
                f"display_name={step.display_name!r})."
            )
        else:
            parts.append(
                "Create exactly one transform step by calling "
                f"transform_step(transform_name={step.search_name!r}, "
                f"parameters={{{params_text}}}, display_name={step.display_name!r})."
            )

    if input_step_ids:
        parts.append(
            f"Use only these resolved graph step IDs as inputs: {input_step_ids!r}. "
            "Do not use planned placeholder IDs from the draft plan."
        )

    parts.append(
        "If the first creation succeeds but needs cleanup, use update_step on the "
        "same graph step instead of creating duplicates."
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
    settings = build_model_settings(config.model_id)

    try:
        with execution_agent.override(model=resolved, model_settings=settings, toolsets=[toolset_for_run]):
            async with execution_agent.iter(
                instruction,
                deps=config.deps,
                usage_limits=usage_limits,
                metadata=config.run_metadata,
            ) as run:
                async for node in run:
                    if Agent.is_model_request_node(node):
                        await stream_model_request(
                            node,
                            run,
                            config.queue,
                            StreamMessageContext(
                                message_id=config.message_id,
                                message_group_id=config.message_group_id,
                                phase=config.phase,
                            ),
                            config.counters,
                        )
                    elif Agent.is_call_tools_node(node):
                        await stream_call_tools(node, run, config.queue, config.deps, config.counters)

                merge_usage(config.counters, run.usage())
                return True
    except Exception as exc:
        logger.exception("Step execution failed", step_id=step.id)
        step.failure_reason = str(exc)
        return False


def _resolve_inputs_for_execution(
    config: PhaseConfig,
    plan: StrategyPlan,
    step: PlannedStep,
    incoming_connections: dict[str, list[PlannedConnection]],
) -> list[str] | None:
    """Resolve authoritative graph inputs for one planned step."""
    graph = config.deps.strategy_session.get_graph(None)
    active_graph_step_ids = set(graph.steps) if graph is not None else set()
    active_root_ids = set(graph.roots) if graph is not None else set()
    return resolve_input_step_ids(
        plan,
        step,
        active_graph_step_ids=active_graph_step_ids,
        active_root_ids=active_root_ids,
        incoming_connections=incoming_connections,
    )


async def _run_step_attempts(
    step: PlannedStep,
    config: PhaseConfig,
    allowed_tools: frozenset[str],
    input_step_ids: list[str] | None,
) -> bool:
    """Run the step once, then retry with the full toolset if needed."""
    try:
        selected_tools = allowed_tools or frozenset()
        success = await run_step_with_agent(
            step,
            config,
            selected_tools,
            EXECUTION_USAGE_LIMITS,
            input_step_ids,
        )
        if not success and allowed_tools:
            logger.info(
                "Step failed, attempting recovery with full toolset",
                step_id=step.id,
                step_type=step.step_type,
            )
            success = await run_step_with_agent(
                step,
                config,
                frozenset(),
                EXECUTION_RECOVERY_LIMITS,
                input_step_ids,
            )
    except Exception as exc:
        logger.exception("Step execution raised an exception", step_id=step.id)
        step.failure_reason = str(exc)
        return False
    else:
        return success


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
    await emit_plan_update(config, active_plan)

    try:
        ordered_steps = active_plan.steps_in_dependency_order()
    except ValueError:
        logger.exception("Plan has cyclic dependencies — falling back to list order")
        ordered_steps = list(active_plan.steps)

    incoming_connections = _build_incoming_connection_index(active_plan)

    execution_failed = False
    for step in ordered_steps:
        step.status = StepStatus.EXECUTING
        await emit_plan_update(config, active_plan)
        allowed = allowed_tools_for_step(step)
        prior_step_ids, prior_roots = _capture_graph_state(config)

        try:
            inputs = _resolve_inputs_for_execution(
                config,
                active_plan,
                step,
                incoming_connections=incoming_connections,
            )
        except StepExecutionResolutionError as exc:
            logger.warning(
                "Planned step input resolution failed",
                step_id=step.id,
                error=str(exc),
            )
            step.failure_reason = str(exc)
            step.status = StepStatus.FAILED
            await emit_plan_update(config, active_plan)
            execution_failed = True
            break

        success = await _run_step_attempts(step, config, allowed, inputs)

        if success:
            try:
                _record_step_mapping(
                    step,
                    config,
                    prior_step_ids=prior_step_ids,
                    prior_roots=prior_roots,
                )
            except StepExecutionResolutionError as exc:
                logger.warning(
                    "Planned step execution produced an invalid mapping",
                    step_id=step.id,
                    error=str(exc),
                )
                step.failure_reason = str(exc)
                success = False

        step.status = StepStatus.COMPLETE if success else StepStatus.FAILED
        if not success:
            logger.warning("Step execution failed", step_id=step.id)
            execution_failed = True
        await emit_plan_update(config, active_plan)
        if execution_failed:
            break

    # Update plan status based on step outcomes.  ``classify_failure`` on the
    # plan inspects per-step ``failure_reason`` values; the phase driver reads
    # that (via ``StrategyPlan.classify_failure``) together with the FSM's
    # replan history to decide between ``replan`` and
    # ``retry_discovery_from_execution``.
    all_complete = all(
        s.status == StepStatus.COMPLETE for s in active_plan.steps
    )
    active_plan.status = PlanStatus.COMPLETE if all_complete else PlanStatus.FAILED
    await emit_plan_update(config, active_plan)
