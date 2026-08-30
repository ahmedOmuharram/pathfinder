"""One reconciled sub-agent call carries exactly one phase name.

The dispatch and the run both report the same call id, so a thread that reads
the phase has to see one vocabulary: ``frame``, ``build`` or ``verification``.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.usage import RunUsage

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.graph._lead_events import (
    _SUB_AGENT_TOOL_TO_PHASE,
    handle_sub_agent_event,
)
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.deltas import RecoveryDelta
from pathfinder.ai.lead.sub_agent_stream import _emit_running_sub_agent_usage

_WIRE_PHASES = frozenset({"frame", "build", "verification"})

_CALL_ID = "sa_1"


def _collect() -> tuple[list[dict[str, Any]], Any]:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    return captured, writer


def _phases(captured: list[dict[str, Any]], call_id: str) -> set[str]:
    return {
        payload["chunk"]["data"]["phase"]
        for payload in captured
        if payload["chunk"]["type"] == "data-sub-agent-call"
        and payload["chunk"]["data"]["toolCallId"] == call_id
    }


@pytest.mark.parametrize(
    ("tool_name", "role"),
    [
        ("frame_problem", "frame"),
        ("edit_strategy", "frame"),
        ("recover_failed_steps", "execution"),
        ("verify_strategy", "verification"),
    ],
)
def test_one_call_id_carries_one_phase_name(
    tool_name: str,
    role: PhaseRole,
) -> None:
    captured, writer = _collect()
    deps: Any = _LeadDepsStub()
    calls: dict[str, str] = {}

    handle_sub_agent_event(
        deps,
        writer,
        FunctionToolCallEvent(
            part=ToolCallPart(
                tool_name=tool_name,
                args={"reason": "why"},
                tool_call_id=_CALL_ID,
            ),
        ),
        calls,
        {},
    )
    _emit_running_sub_agent_usage(writer, role, _CALL_ID, RunUsage())
    handle_sub_agent_event(
        deps,
        writer,
        FunctionToolResultEvent(
            part=ToolReturnPart(
                tool_name=tool_name,
                content=RecoveryDelta(),
                tool_call_id=_CALL_ID,
            ),
        ),
        calls,
        {},
    )

    phases = _phases(captured, _CALL_ID)
    assert len(phases) == 1, phases
    assert phases <= _WIRE_PHASES


def test_the_wire_vocabulary_is_frame_build_and_verification() -> None:
    assert set(_SUB_AGENT_TOOL_TO_PHASE.values()) == _WIRE_PHASES


class _LeadDepsStub:
    """Enough of the Lead's deps for the card and the ledger refresh."""

    def __init__(self) -> None:
        self.state = PipelineState(
            conversation_id=uuid4(),
            user_id=uuid4(),
            site_id="plasmodb",
            mode="strategy",
            user_prompt="recover the failed steps",
        )
        self.intent = None
