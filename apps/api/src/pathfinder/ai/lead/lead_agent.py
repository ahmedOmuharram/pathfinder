"""The Lead Agent — the user's voice and the only LLM in the dispatcher.

The Lead orchestrates the investigation by calling sub-agent tools, reads
the typed Ledger to know what's true after each call, and produces the
single user-facing voice. Phases are not nodes; they are tools the Lead
decides to invoke. There is no deterministic supervisor — the Lead is
the brain.

Tool surface (in three groups):

  Reasoning / inspection
    - ``classify_user_intent`` — sets the typed UserIntent on deps once
      per turn. The Lead calls this first.
    - ``read_ledger_section`` — fetch full detail of a Ledger section
      (frame / discovery / plan / build / verification). The Lead reads
      a compact summary in pinned instructions; this lets it drill in
      when a section's counts indicate something needs attention.

  Sub-agent tools (work-order wrappers around phase agents)
    - ``scope_problem`` — runs the scoping sub-agent.
    - ``discover_searches`` — runs the discovery sub-agent (with hints).
    - ``build_plan`` — runs the planning sub-agent.
    - ``execute_plan`` — declarative no-LLM build of an APPROVED plan.
    - ``recover_failed_steps`` — runs the LLM execution-recovery agent.
    - ``verify_strategy`` — runs the verification sub-agent.

  User-touching (both deferred-tools that pause with a ToolApprovalRequest)
    - ``consult_user`` — ask the user design questions that shape the
      investigation BEFORE a plan is finalized. The carousel renders them
      as question slides (options + free-text note); answers come back to
      the Lead, which re-runs build_plan honoring them.
    - ``submit_plan_for_approval`` — clean go/no-go on a settled plan. The
      plan card surfaces remaining NEEDS_USER_INPUT slots as form fields;
      on approval the body applies slot answers and marks the plan APPROVED.

The Lead's final output is a ``LeadResponse`` containing user-facing
prose and a turn-state literal (``await_user`` vs ``complete``). All
intent classification, sub-agent dispatch, and slot logic happen via
tools; the ``prose`` field is purely user-facing copy.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_ai import Agent, DeferredToolRequests, RunContext, Tool
from pydantic_ai.capabilities import ProcessHistory, Thinking
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.graph.state import ConsultQuestion, UserQuestionAnswer
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.slot_answers import (
    apply_plan_slot_answers,
    assert_no_unresolved_slots,
    mark_plan_approved,
)
from pathfinder.ai.lead.sub_agent_dispatch import (
    build_plan,
    discover_searches,
    execute_plan,
    recover_failed_steps,
    scope_problem,
    verify_strategy,
)
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone._stream_parts import plan_artifact_chunk
from pathfinder.ai.tools.standalone.control_sets import (
    build_control_set,
    import_control_ids_from_gene_set,
    import_control_ids_from_strategy,
    list_control_sets,
)
from pathfinder.ai.tools.standalone.plan import (
    planned_steps_for_stream,
    slot_forms_for_stream,
)
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.ai.tools.standalone.variant_comparison import compare_search_variants
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel

LeadTurnState = Literal["await_user", "complete"]
LedgerSectionName = Literal[
    "frame",
    "discovery",
    "plan",
    "build",
    "verification",
]


class LeadResponse(CamelModel):
    """The Lead's final user-facing turn output.

    ``prose`` is rendered to the user verbatim (no upstream/downstream
    translation). ``next_state`` tells the dispatcher whether the turn is
    paused waiting on the user (``await_user``) or fully resolved
    (``complete`` — typically after a successful verification).
    """

    prose: str = Field(
        max_length=4000,
        description=(
            "User-facing reply for this turn. Plain markdown. Do NOT "
            "include sub-agent log noise — synthesize from the Ledger."
        ),
    )
    next_state: LeadTurnState = "await_user"


def pinned_ledger_summary(ctx: RunContext[LeadDeps]) -> str:
    """Compact Ledger summary, derived fresh each instruction render."""
    ledger = derive_ledger(ctx.deps.state, ctx.deps.intent)
    return ledger.render_summary()


def pinned_user_intent(ctx: RunContext[LeadDeps]) -> str | None:
    intent = ctx.deps.intent
    if intent is None:
        return (
            "## User Intent\nNot classified yet. Call ``classify_user_intent`` first."
        )
    lines = [
        "## User Intent",
        f"- classification: {intent.classification.value}",
        f"- inferred goal: {intent.inferred_goal}",
    ]
    if intent.is_differential and intent.differential_sides:
        lines.append(f"- differential sides: {intent.differential_sides}")
    if intent.referenced_step_ids:
        lines.append(f"- referenced steps: {intent.referenced_step_ids}")
    if intent.referenced_strategy_ids:
        lines.append(
            f"- referenced strategies: {intent.referenced_strategy_ids}",
        )
    return "\n".join(lines)


def pinned_user_prompt(ctx: RunContext[LeadDeps]) -> str | None:
    prompt = ctx.deps.state.user_prompt
    if not prompt:
        return None
    return f"## User's latest message\n{prompt}"


def classify_user_intent(
    ctx: RunContext[LeadDeps],
    intent: UserIntent,
) -> UserIntent:
    """Classify the user's intent for this turn. Call this exactly once,
    before any other sub-agent call.

    Construct a ``UserIntent`` with: ``raw_text`` (the user's literal
    message), ``classification`` (one of the IntentClassification enum
    values), ``inferred_goal`` (your one-sentence paraphrase),
    ``is_differential`` and ``differential_sides`` when the user is
    asking a comparison question, and any referenced step/strategy IDs.
    """
    ctx.deps.intent = intent
    return intent


def read_ledger_section(
    ctx: RunContext[LeadDeps],
    section: LedgerSectionName,
) -> str:
    """Return the full detail of one Ledger section.

    The pinned summary already shows counts and derived booleans; use
    this when you need step-level detail (failed step IDs, open slot
    questions, fit-report rationales) before deciding the next move.
    """
    ledger = derive_ledger(ctx.deps.state, ctx.deps.intent)
    return ledger.render_section(section)


async def submit_plan_for_approval(
    ctx: RunContext[LeadDeps],
) -> ToolReturn[StrategyPlan]:
    """Surface the active plan to the user for approval.

    Registered with ``requires_approval=True`` — the agent halts on the
    first call with a ``DeferredToolRequests``; pydantic-ai emits a
    ``ToolApprovalRequest`` chunk that the dispatcher converts into a
    ``data-tool-approval-request`` SSE event. The plan card renders
    NEEDS_USER_INPUT slots as inline form fields.

    On approval, the body resumes with ``DeferredToolResults({id: True})``.
    Slot answers arrive on ``state.plan_slot_answers[tool_call_id]``;
    we apply them, refuse the submission if any NEEDS_DISCOVERY remains,
    then mark the plan APPROVED and emit a ``data-plan-artifact`` chunk
    so the frontend re-renders the form-free approved card.
    """
    state = ctx.deps.state
    plan = state.active_plan
    if plan is None:
        msg = (
            "NO_ACTIVE_PLAN: cannot submit a plan that doesn't exist. "
            "Call build_plan first."
        )
        raise ModelRetry(msg)

    pending = state.pending_approval
    answers = (
        list(state.plan_slot_answers.get(pending.tool_call_id, []))
        if pending is not None
        else []
    )
    apply_plan_slot_answers(plan, answers)
    assert_no_unresolved_slots(plan)
    mark_plan_approved(plan)

    metadata: list[DataChunk] = [
        plan_artifact_chunk(
            plan_id=plan.id,
            steps=planned_steps_for_stream(plan),
            rationale=plan.rationale or "",
            slots=slot_forms_for_stream(plan),
        ),
    ]
    return ToolReturn(return_value=plan, metadata=metadata)


def _format_answers(answers: list[UserQuestionAnswer]) -> str:
    parts: list[str] = []
    for a in answers:
        chosen = ", ".join(a.chosen_labels) if a.chosen_labels else "(free text)"
        line = f'"{a.prompt}" → {chosen}'
        if a.note:
            line += f" — note: {a.note}"
        parts.append(line)
    return "; ".join(parts)


async def consult_user(
    ctx: RunContext[LeadDeps],
    questions: list[ConsultQuestion],
) -> ToolReturn[list[UserQuestionAnswer]]:
    """Ask the user design questions that SHAPE the investigation, before a
    plan is built. Use this whenever a real fork exists — which searches to
    combine, a threshold that changes the steps, whether to add an arm —
    instead of guessing or bundling the choice into plan approval.

    This pauses the turn: the user answers each question in a carousel
    (options + optional free-text note). Their answers are returned to you
    here so you can run (or re-run) ``build_plan`` with them as hard
    constraints. Ask only the few questions that genuinely change the
    answer; pick sensible defaults for everything else and state your
    assumptions in prose. Do NOT ask "submit or request changes?" — the
    approval card already offers both.
    """
    state = ctx.deps.state
    pending = state.pending_approval
    answers = (
        list(state.user_question_answers.get(pending.tool_call_id, []))
        if pending is not None
        else []
    )
    if not answers:
        return ToolReturn(
            return_value=answers,
            content=(
                f"Presented {len(questions)} question(s); awaiting the user's answers."
            ),
        )
    return ToolReturn(
        return_value=answers,
        content=(
            f"The user answered your questions: {_format_answers(answers)}. "
            "Now run build_plan honoring these as hard constraints."
        ),
    )


async def _require_active_plan(
    ctx: RunContext[LeadDeps], tool_def: ToolDefinition
) -> ToolDefinition | None:
    """Hide ``submit_plan_for_approval`` until a plan actually exists, so the
    Lead can't halt for approval on a non-existent plan — it must call
    ``build_plan`` first."""
    return tool_def if ctx.deps.state.active_plan is not None else None


_submit_plan_tool: Tool[LeadDeps] = Tool(
    submit_plan_for_approval,
    requires_approval=True,
    prepare=_require_active_plan,
)

_consult_user_tool: Tool[LeadDeps] = Tool(
    consult_user,
    requires_approval=True,
)


lead_agent: Agent[LeadDeps, LeadResponse | DeferredToolRequests] = Agent(
    "openai:gpt-4.1",
    output_type=[LeadResponse, DeferredToolRequests],
    deps_type=LeadDeps,
    instructions=LEAD_INSTRUCTIONS,
    tools=[
        Tool(classify_user_intent),
        Tool(read_ledger_section),
        Tool(scope_problem),
        Tool(discover_searches),
        Tool(build_plan),
        Tool(execute_plan),
        Tool(recover_failed_steps),
        Tool(verify_strategy),
        Tool(compare_search_variants),
        Tool(build_control_set),
        Tool(list_control_sets),
        Tool(import_control_ids_from_gene_set),
        Tool(import_control_ids_from_strategy),
        Tool(compare_variants_scored),
        _consult_user_tool,
        _submit_plan_tool,
    ],
    capabilities=[
        Thinking(effort="high"),
        *(ProcessHistory[LeadDeps](p) for p in PHASE_HISTORY_PROCESSORS),
    ],
    retries=3,
    description="The user's voice — orchestrates sub-agents via the Ledger",
    name="lead",
    defer_model_check=True,
)


for _fn in (pinned_user_prompt, pinned_user_intent, pinned_ledger_summary):
    lead_agent.instructions(_fn)
