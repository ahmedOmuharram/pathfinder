from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from pathfinder.ai.graph.state import (
    PhaseName,
    SupervisorEvent,
    SupervisorEventKind,
)
from pathfinder.ai.graph.supervisor_log import record_supervisor_event


async def journal(
    ctx: RunContext[Any],
    kind: SupervisorEventKind,
    summary: str,
    detail: str | None = None,
    phase: PhaseName | None = None,
    refs: list[str] | None = None,
) -> str:
    """Append a durable note to the supervisor's running orchestrator log.

    Use ONLY for facts the supervisor needs across phase boundaries:
    plan-level decisions, observed loops, why a phase was rejected, etc.
    The note shows in the orchestrator panel and is prepended to the
    supervisor's instructions on every future turn.

    ``kind=supervisor_note`` for free-form thoughts; ``plan_event`` /
    ``build_outcome`` for structured facts; ``route`` / ``approval`` etc.
    when describing a control decision.
    """
    deps: Any = ctx.deps
    log: list[SupervisorEvent] = deps.supervisor_log
    writer: Any = deps.writer
    record_supervisor_event(
        log,
        writer,
        SupervisorEvent(
            kind=kind,
            summary=summary,
            detail=detail,
            phase=phase,
            refs=refs or [],
        ),
    )
    return "noted"
