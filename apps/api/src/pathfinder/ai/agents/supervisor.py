from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.models.catalog import ModelEntry, get_smallest_model
from pathfinder.platform.config import get_settings
from pathfinder.platform.types import ModelProvider

SupervisorTarget = Literal[
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
    "end",
]


class SupervisorDecision(BaseModel):
    to: SupervisorTarget
    reason: str = Field(min_length=1, max_length=280)


_SUPERVISOR_INSTRUCTIONS = """\
You are the Supervisor for PathFinder's five-phase research pipeline. You \
do not call tools or talk to the user. You read the current turn state and \
choose the next node to run: scoping, discovery, planning, execution, \
verification, or `end` to finish the user's turn.

## The Phases

- **scoping** — frame the biological problem, ask blocking questions, save \
a Problem Frame.
- **discovery** — explore the WDK catalog for candidate searches, \
parameters, and literature context.
- **planning** — synthesize discovery findings into a concrete execution \
plan (searches, operators, parameters).
- **execution** — apply the plan to the strategy graph via WDK tools.
- **verification** — inspect results, run controls, summarize outcome.
- **end** — stop this turn. The server will flush the assistant's prose \
and wait for the next user message.

## Your Decision

Pick exactly ONE target and write ONE short sentence explaining why. The \
`reason` is user-visible (a small chip in the chat) and appears in logs.

You may jump to ANY phase including backward (planning -> discovery, \
execution -> planning, verification -> execution). There are no forced \
transitions.

## How to Decide (common cases)

- The last agent asked a blocking question in its prose -> pick `end` so \
the user can answer.
- User just answered a scoping question -> pick `scoping` to fold it into \
the frame, or `discovery` if the frame is already resolved.
- Scoping produced a solid Problem Frame and no open blocking questions -> \
pick `discovery`.
- The user's intent is so specific that discovery is superfluous -> skip \
to `planning`.
- Discovery found concrete candidate searches and parameter choices -> \
pick `planning`.
- Planning reveals the catalog findings are insufficient -> go back to \
`discovery`.
- A plan has been submitted -> pick `execution`.
- Execution finished all planned steps successfully -> pick `verification`.
- Execution's plan is broken fundamentally (wrong searches, not fixable \
parameters) -> go back to `planning` (or `discovery` if the searches \
themselves are wrong).
- Verification passed or the turn's result is ready -> pick `end`.
- Verification surfaced an execution bug (bad params, wrong filter) -> go \
back to `execution`.
- Verification shows the strategy's shape is wrong -> go back to `planning`.
- User asked a fresh, unrelated question that invalidates the frame -> \
pick `scoping`.
- You have already run many phases this turn and nothing new is happening -> \
pick `end` to avoid loops.

Prefer `end` when in doubt: users can always reply and the pipeline will \
re-enter. Forward-progress only when there is concrete new work to do.
"""

_SUPERVISOR_USAGE_LIMITS = UsageLimits(
    request_limit=2,
    total_tokens_limit=4_000,
)


def _pydantic_ai_model_id(entry: ModelEntry) -> str:
    return f"{entry.provider}:{entry.model}"


def build_supervisor_agent(
    provider: ModelProvider | None = None,
) -> Agent[None, SupervisorDecision]:
    resolved: ModelProvider = provider or get_settings().default_provider
    entry = get_smallest_model(resolved)
    return Agent(
        _pydantic_ai_model_id(entry),
        output_type=SupervisorDecision,
        instructions=_SUPERVISOR_INSTRUCTIONS,
        retries=2,
        name="supervisor",
        defer_model_check=True,
    )


SUPERVISOR_USAGE_LIMITS: UsageLimits = _SUPERVISOR_USAGE_LIMITS
