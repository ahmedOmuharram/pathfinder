from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, RunContext
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
    "reject",
    "question",
]


class SupervisorDecision(BaseModel):
    to: SupervisorTarget
    reason: str = Field(min_length=1, max_length=280)
    rejection_message: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _require_payload_for_special_kinds(self) -> SupervisorDecision:
        if self.to == "reject":
            if not self.rejection_message or not self.rejection_message.strip():
                msg = "rejection_message is required when to='reject'"
                raise ValueError(msg)
        if self.to == "question":
            if not self.answer or not self.answer.strip():
                msg = "answer is required when to='question'"
                raise ValueError(msg)
        return self


@dataclass
class SupervisorDeps:
    state_block: str


_SUPERVISOR_INSTRUCTIONS = """\
You supervise an iterative 5-phase research pipeline:

  scoping → discovery → planning → execution → verification

The order is typical, not forced. Any phase may jump to any other phase. \
Investigations often revisit scoping to refine a frame, go back to \
discovery when planning reveals gaps, or re-plan after execution \
surfaces issues. Most complete investigations hit all five phases \
eventually, in some order.

Investigation state persists across turns (Problem Frame, Active Plan, \
prior phase outputs — delivered to you via message history). Use it.

## Actions

**Phase routes** — continue the pipeline:
- `scoping` — frame or refine the biological problem.
- `discovery` — search the WDK catalog and literature.
- `planning` — build or update the execution plan.
- `execution` — apply the plan to the strategy graph.
- `verification` — inspect results, run controls, report.

**Turn-level responses** — answer this user message without running a \
phase. These do NOT end the investigation; the next user message can \
resume phase work with full state intact.
- `question` — respond with a direct answer. Appropriate for pure \
conceptual/definitional asks at any point in the investigation.
- `reject` — politely decline. Appropriate when the user's message is \
plainly off-topic for biological research, even mid-investigation.

**Turn termination**:
- `end` — stop processing this turn. Use when the most recent phase has \
produced a response the user should read, when waiting for user input, \
or when you've already run enough phases this turn and no new forward \
progress is possible.

## Choosing

Judge the user's intent from the message and chat state, then pick the \
action that matches:

- **Phase routes** — the user's message carries research intent: a \
biological goal, a refinement or correction, an answer to a clarifying \
question, a request to continue or inspect prior work.
- **`question`** — the user's message does not carry research intent \
but is still in-scope conversation: social/meta, conceptual/\
methodological, tool/UI questions. A direct one-shot reply is enough.
- **`reject`** — the user's message is out of scope for biological \
research.
- **`end`** — the phase that just ran this turn has already produced \
the response the user should see, or repeated supervisor calls have \
made no new progress.

Hard constraints:

- Message history and Pipeline State are authoritative for what has \
already happened. Use them.
- References to prior work carry research intent — route to a phase, \
not `question`.
- `question` and `reject` replace phase output; they can't stack on \
top of one. If any phase has already run this turn, `question` and \
`reject` are invalid — pick `end` or another phase route.
- Each phase runs at most once per turn. If a phase appears in \
phase_call_counts_this_turn, do not route to it again this turn.

## Response format

Pick one action and write one short sentence in `reason`. For `reject`, \
fill `rejection_message`. For `question`, fill `answer`. The \
message/answer and reason are both shown to the user.
"""

_SUPERVISOR_USAGE_LIMITS = UsageLimits(
    request_limit=2,
    total_tokens_limit=6_000,
)


def _pydantic_ai_model_id(entry: ModelEntry) -> str:
    return f"{entry.provider}:{entry.model}"


def build_supervisor_agent(
    provider: ModelProvider | None = None,
) -> Agent[SupervisorDeps, SupervisorDecision]:
    resolved: ModelProvider = provider or get_settings().default_provider
    entry = get_smallest_model(resolved)
    agent: Agent[SupervisorDeps, SupervisorDecision] = Agent(
        _pydantic_ai_model_id(entry),
        deps_type=SupervisorDeps,
        output_type=SupervisorDecision,
        instructions=_SUPERVISOR_INSTRUCTIONS,
        retries=2,
        name="supervisor",
        defer_model_check=True,
    )

    @agent.instructions
    def _pipeline_state(ctx: RunContext[SupervisorDeps]) -> str:
        return ctx.deps.state_block

    return agent


SUPERVISOR_USAGE_LIMITS: UsageLimits = _SUPERVISOR_USAGE_LIMITS
