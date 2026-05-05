from __future__ import annotations

from typing import Any

from pathfinder.ai.graph.state import SupervisorEvent
from pathfinder.ai.graph.stream_events import supervisor_context_event


def record_supervisor_event(
    log: list[SupervisorEvent],
    writer: Any,
    event: SupervisorEvent,
) -> SupervisorEvent:
    log.append(event)
    if writer is not None:
        chunk = supervisor_context_event(
            kind=event.kind,
            summary=event.summary,
            detail=event.detail,
            phase=event.phase,
            refs=event.refs,
            at=event.at.isoformat(),
        )
        writer(
            {
                "chunk": chunk.model_dump(
                    by_alias=True, mode="json", exclude_none=True,
                ),
            },
        )
    return event


def format_supervisor_log(events: list[SupervisorEvent]) -> str:
    if not events:
        return ""
    lines = ["## Orchestrator running context"]
    for ev in events:
        prefix = f"- [{ev.kind}"
        if ev.phase is not None:
            prefix += f"/{ev.phase}"
        prefix += "]"
        lines.append(f"{prefix} {ev.summary}")
        if ev.detail:
            lines.extend(f"    {d}" for d in ev.detail.splitlines())
    return "\n".join(lines)
