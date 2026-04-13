"""State-machine phase driving for streamed chat turns."""

import asyncio
from collections.abc import Callable

from pydantic_ai.messages import ModelMessage

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    PhaseDecision,
    PhaseName,
)
from pathfinder.ai.orchestration.pipeline import AgentPipeline
from pathfinder.domain.strategy.plan import FailureKind, PlanStatus
from pathfinder.platform.logging import get_logger
from pathfinder.platform.turn_metadata import read_failure_kind
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.phase_recovery import (
    recover_missing_phase_decision,
)
from pathfinder.services.chat.streaming.phase_runner import (
    PhaseConfig,
    run_phase,
)
from pathfinder.services.chat.streaming.step_execution import run_execution_phase
from pathfinder.services.chat.streaming.turn_lifecycle import _emit_phase_status
from pathfinder.services.chat.streaming.turn_telemetry import (
    PhaseEventContext,
    PhaseTimingTracker,
)

logger = get_logger(__name__)


class MissingPhaseDecisionError(ValueError):
    """Raised when a phase exits without declaring how it should end."""

    def __init__(self, phase: str) -> None:
        super().__init__(
            f"{phase.title()} phase must call finish_{phase} before exiting."
        )


def _phase_decision(deps: AgentDeps, phase: PhaseName) -> PhaseDecision | None:
    """Return the stored :class:`PhaseDecision` for *phase*, or ``None``.

    Typed dispatch over the ``PhaseName`` literal union — no
    :func:`getattr` by string, so mypy can still check the result types.
    """
    match phase:
        case "scoping":
            return deps.scoping_result.decision if deps.scoping_result else None
        case "discovery":
            return deps.discovery_result.decision if deps.discovery_result else None
        case "planning":
            return deps.planning_result.decision if deps.planning_result else None
        case "verification":
            return (
                deps.verification_result.decision
                if deps.verification_result
                else None
            )


def _require_phase_decision(deps: AgentDeps, phase: PhaseName) -> PhaseDecision:
    """Return the declared phase decision or fail fast if the phase drifted."""
    decision = _phase_decision(deps, phase)
    if decision is None or decision.phase != phase:
        raise MissingPhaseDecisionError(phase)
    return decision


def _phase_assistant_text(config: PhaseConfig) -> str:
    return "\n\n".join(config.counters.accumulated_text_parts).strip()


def _resolve_phase_decision(
    config: PhaseConfig,
    phase: PhaseName,
    *,
    record_recovery: Callable[[str, str, str, JSONObject | None], None] | None = None,
) -> PhaseDecision:
    try:
        return _require_phase_decision(config.deps, phase)
    except MissingPhaseDecisionError:
        recovered_decision = recover_missing_phase_decision(
            config.deps,
            phase,
            assistant_text=_phase_assistant_text(config),
            record_recovery=record_recovery,
        )
        if recovered_decision is None:
            raise
        return recovered_decision


async def _pause_for_user_input(
    config: PhaseConfig,
    phase_timings: PhaseTimingTracker,
    *,
    phase: str,
    phase_ctx: PhaseEventContext,
) -> bool:
    """Emit the awaiting_input event for a phase and stop the pipeline."""
    await _emit_phase_status(
        config.queue,
        phase_ctx=phase_ctx,
        snapshot=phase_timings.snapshot(phase, "awaiting_input"),
        message_id=config.message_id,
        message_group_id=config.message_group_id,
    )
    return True


async def _run_scoping_phase(
    config: PhaseConfig,
    phase_timings: PhaseTimingTracker,
    phase_ctx: PhaseEventContext,
    *,
    record_recovery: Callable[[str, str, str, JSONObject | None], None] | None = None,
) -> tuple[list[ModelMessage], bool]:
    """Run scoping and return whether the pipeline should pause."""
    phase_messages = await run_phase(config)
    decision = _resolve_phase_decision(
        config,
        "scoping",
        record_recovery=record_recovery,
    )
    if decision.decision == "ask_user":
        return phase_messages, await _pause_for_user_input(
            config,
            phase_timings,
            phase="scoping",
            phase_ctx=phase_ctx,
        )
    return phase_messages, False


async def _run_discovery_phase(
    config: PhaseConfig,
    phase_timings: PhaseTimingTracker,
    phase_ctx: PhaseEventContext,
    *,
    record_recovery: Callable[[str, str, str, JSONObject | None], None] | None = None,
) -> tuple[list[ModelMessage], bool]:
    """Run discovery and return whether the pipeline should pause."""
    phase_messages = await run_phase(config)
    decision = _resolve_phase_decision(
        config,
        "discovery",
        record_recovery=record_recovery,
    )
    if decision.decision == "ask_user":
        return phase_messages, await _pause_for_user_input(
            config,
            phase_timings,
            phase="discovery",
            phase_ctx=phase_ctx,
        )
    return phase_messages, False


async def _run_planning_phase(
    sm: AgentPipeline,
    config: PhaseConfig,
    phase_timings: PhaseTimingTracker,
    phase_ctx: PhaseEventContext,
    *,
    record_recovery: Callable[[str, str, str, JSONObject | None], None] | None = None,
) -> bool:
    """Run planning and return whether the pipeline should pause."""
    await run_phase(config)
    decision = _resolve_phase_decision(
        config,
        "planning",
        record_recovery=record_recovery,
    )
    if decision.decision == "ask_user":
        return await _pause_for_user_input(
            config,
            phase_timings,
            phase="planning",
            phase_ctx=phase_ctx,
        )
    sm.send("submit_draft")
    if await check_plan_approval(
        config.deps,
        config.queue,
        phase_timings,
        phase_ctx=phase_ctx,
        message_id=config.message_id,
        message_group_id=config.message_group_id,
    ):
        return True
    sm.send("approve")
    return False


async def _run_execution_state_phase(
    sm: AgentPipeline,
    config: PhaseConfig,
) -> None:
    """Run execution and advance to rediscovery, replanning, or verification."""
    await run_execution_phase(config)
    plan = config.deps.agent_state.active_plan
    if plan is not None and plan.status == PlanStatus.FAILED:
        # Prefer an explicit classification written by the executor; fall back
        # to the plan-level heuristic informed by the FSM's planning history.
        failure_kind = read_failure_kind(config.deps.turn_metadata)
        if failure_kind is None:
            failure_kind = plan.classify_failure(
                planning_attempts=sm.retry_counts.get("planning", 0),
            )
        if failure_kind == FailureKind.SEARCH_INVALID and sm.needs_rediscovery():
            logger.info(
                "Execution failed with invalid search, rediscovering",
                attempt=sm.retry_counts.get("discovery", 0),
                budget=sm.retry_budget,
            )
            sm.send("retry_discovery_from_execution")
            return
        if sm.should_replan():
            logger.info(
                "Execution failed, replanning",
                attempt=sm.retry_counts.get("execution", 0),
                budget=sm.retry_budget,
            )
            sm.send("replan")
            return
    sm.send("finish_execution")


async def _run_verification_phase(
    config: PhaseConfig,
    phase_timings: PhaseTimingTracker,
    phase_ctx: PhaseEventContext,
    *,
    record_recovery: Callable[[str, str, str, JSONObject | None], None] | None = None,
) -> bool:
    """Run verification and return whether the pipeline should pause."""
    await run_phase(config)
    decision = _resolve_phase_decision(
        config,
        "verification",
        record_recovery=record_recovery,
    )
    if decision.decision == "ask_user":
        return await _pause_for_user_input(
            config,
            phase_timings,
            phase="verification",
            phase_ctx=phase_ctx,
        )
    return False


async def check_plan_approval(
    deps: AgentDeps,
    queue: asyncio.Queue[JSONObject],
    phase_timings: PhaseTimingTracker,
    *,
    phase_ctx: PhaseEventContext,
    message_id: str,
    message_group_id: str | None,
) -> bool:
    """Check if the plan needs user approval. Returns True to pause the pipeline."""
    active_plan = deps.agent_state.active_plan
    if active_plan is None or active_plan.status != PlanStatus.PRESENTED:
        return False
    await _emit_phase_status(
        queue,
        phase_ctx=phase_ctx,
        snapshot=phase_timings.snapshot("planning", "awaiting_approval"),
        message_id=message_id,
        message_group_id=message_group_id,
    )
    return True


async def run_sm_phase(
    sm: AgentPipeline,
    config: PhaseConfig,
    discovery_messages: list[ModelMessage] | None,
    phase_timings: PhaseTimingTracker,
    phase_ctx: PhaseEventContext,
    *,
    record_recovery: Callable[[str, str, str, JSONObject | None], None] | None = None,
) -> tuple[list[ModelMessage] | None, bool]:
    """Execute one StateChart phase and advance the machine.

    Returns ``(discovery_messages, should_break)``.
    """
    phase = config.phase
    if phase == "execution":
        await _run_execution_state_phase(sm, config)
    elif phase == "scoping":
        discovery_messages, should_break = await _run_scoping_phase(
            config,
            phase_timings,
            phase_ctx,
            record_recovery=record_recovery,
        )
        if should_break:
            return discovery_messages, True
        sm.send("finish_scoping")
    elif phase == "discovery":
        discovery_messages, should_break = await _run_discovery_phase(
            config,
            phase_timings,
            phase_ctx,
            record_recovery=record_recovery,
        )
        if should_break:
            return discovery_messages, True
        sm.send("finish_discovery")
    elif phase == "planning":
        if await _run_planning_phase(
            sm,
            config,
            phase_timings,
            phase_ctx,
            record_recovery=record_recovery,
        ):
            return discovery_messages, True
    elif phase == "verification":
        if await _run_verification_phase(
            config,
            phase_timings,
            phase_ctx,
            record_recovery=record_recovery,
        ):
            return discovery_messages, True
        sm.send("finish_verification")
    return discovery_messages, False
