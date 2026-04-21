from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, RunContext

from pathfinder.ai.agents._history_processor import pair_tool_calls
from pathfinder.ai.agents._model_resolution import (
    resolve_orchestrator_model_entry,
)
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
        if self.to == "reject" and (
            not self.rejection_message or not self.rejection_message.strip()
        ):
            msg = "rejection_message is required when to='reject'"
            raise ValueError(msg)
        if self.to == "question" and (
            not self.answer or not self.answer.strip()
        ):
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
- `end` — stop processing this turn. Appropriate when the most recent \
phase has produced output the user should read and no further phase \
work is warranted without user input.

## The `last_phase_prose_to_user` gate

The pipeline state includes `last_phase_prose_to_user` — the prose the \
most recent phase wrote to the user on this turn. READ IT. The phase \
agent is the voice of the assistant; its prose tells you what the \
assistant is signalling:

- The prose asks a question (literal "?", "Do you want…", "Shall I…", \
"Could you clarify…"), offers explicit options ("Let me know if you'd \
like me to… or…"), or otherwise hands the turn back to the user → pick \
`end`. Running another phase would talk over the user's expected reply.
- The prose is a terminal status update ("strategy built: 152 genes. \
Link above.") with no solicitation of user input → pick `end` if \
verification already ran, else continue the pipeline.
- The prose is a neutral mid-process log ("found 3 candidate searches, \
proceeding to planning") → continue the pipeline.

This is YOUR primary halt signal. Do not talk yourself past a phase's \
explicit hand-off to the user by rationalising that its questions are \
"not really blocking" or "just clarifying". If the phase is talking to \
the user, the user gets to reply next.

## Choosing (when no halt signal)

- **Phase routes** — the user's message carries research intent: a \
biological goal, a refinement or correction, an answer to a clarifying \
question, a request to continue or inspect prior work.
- **`question`** — the user's message does not carry research intent \
but is still in-scope conversation: social/meta, conceptual/\
methodological, tool/UI questions. A direct one-shot reply is enough.
- **`reject`** — the user's message is out of scope for biological \
research.

Hard constraints:

- Message history and Pipeline State are authoritative for what has \
already happened. Use them.
- References to prior work carry research intent — route to a phase, \
not `question`.
- `question` and `reject` replace phase output; they can't stack on \
top of one. If any phase has already run this turn, `question` and \
`reject` are invalid — pick `end` or another phase route.
- Each phase runs at most once per turn. If a phase appears in \
phase_call_counts_this_turn, do not route to it again this turn — pick \
`end` or a different phase.

## Response format

Pick one action and write one short sentence in `reason`. For `reject`, \
fill `rejection_message`. For `question`, fill `answer`. The \
message/answer and reason are both shown to the user.
"""


def build_supervisor_agent(
    provider: ModelProvider | None = None,
    *,
    model_id: str | None = None,
) -> Agent[SupervisorDeps, SupervisorDecision]:
    entry = resolve_orchestrator_model_entry(model_id, provider)
    agent: Agent[SupervisorDeps, SupervisorDecision] = Agent(
        entry.id,
        deps_type=SupervisorDeps,
        output_type=SupervisorDecision,
        instructions=_SUPERVISOR_INSTRUCTIONS,
        history_processors=[pair_tool_calls],
        retries=2,
        name="supervisor",
        defer_model_check=True,
    )

    @agent.instructions
    def _pipeline_state(ctx: RunContext[SupervisorDeps]) -> str:
        return ctx.deps.state_block

    return agent
