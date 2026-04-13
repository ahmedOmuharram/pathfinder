"""Per-turn pipeline context for the new AI-SDK chat dispatcher.

Holds everything a single ``POST /api/v2/chat`` turn needs to flow from the
transport layer through the state machine: the incoming prompt, the parsed
message history (in pydantic-ai ``ModelMessage`` form), the client-supplied
metadata (site id, mode, pipeline override), and the accumulator for the
assistant message's parts and per-phase decisions.

Named ``DispatcherChatContext`` (not just ``ChatContext``) because
``services.chat.types.ChatContext`` already exists as the legacy v1
transport context. The two coexist until Task 7 deletes the old one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic_ai.messages import ModelMessage

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)

PhaseDecision = (
    ScopingDecision
    | DiscoveryDecision
    | PlanningDecision
    | ExecutionDecision
    | VerificationDecision
)


@dataclass
class DispatcherChatContext:
    """Per-turn state passed through the pipeline dispatcher."""

    chat_id: UUID
    user_id: UUID
    user_message_id: UUID
    user_prompt: str
    message_history: list[ModelMessage]
    site_id: str
    mode: str
    pipeline_config: dict[str, Any] | None
    collected_parts: list[dict[str, Any]] = field(default_factory=list)
    phase_decisions: dict[str, PhaseDecision] = field(default_factory=dict)
    current_phase: str | None = None
    turn_trace_id: str | None = None
    turn_created_at: str | None = None

    def record_phase_completion(
        self, phase: str, decision: PhaseDecision
    ) -> None:
        """Remember a phase's ``PhaseDecision`` for later persistence/debug."""
        self.phase_decisions[phase] = decision
        self.current_phase = phase
