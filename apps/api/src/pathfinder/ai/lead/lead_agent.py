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
      (frame / build / verification). The Lead reads a compact summary in
      pinned instructions; this lets it drill in when a section's counts
      indicate something needs attention.

  Sub-agent tools (work-order wrappers around phase agents)
    - ``frame_problem`` — runs FRAME: operationalize the goal into criteria,
      bind each to a real WDK search, resolve params → an OperationalSpec.
    - ``build_strategy`` — declarative no-LLM materialization of the spec
      into a real WDK strategy.
    - ``recover_failed_steps`` — runs the LLM execution-recovery agent.
    - ``verify_strategy`` — runs the verification sub-agent.

  User-touching (deferred-tool that pauses with a ToolApprovalRequest)
    - ``consult_user`` — ask the user design questions that shape the
      investigation at a genuine fork (which arm to add, a threshold that
      changes the steps). The carousel renders them as question slides
      (options + free-text note); answers come back to the Lead.

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
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.graph.state import ConsultQuestion, UserQuestionAnswer
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.live_state import LiveStrategyState, read_live_state
from pathfinder.ai.lead.sub_agent_dispatch import (
    build_strategy,
    frame_problem,
    recover_failed_steps,
    verify_strategy,
)
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone.control_sets import (
    build_control_set,
    import_control_ids_from_gene_set,
    import_control_ids_from_strategy,
    list_control_sets,
)
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.ai.tools.standalone.variant_comparison import compare_search_variants
from pathfinder.platform.pydantic_base import CamelModel

LeadTurnState = Literal["await_user", "complete"]
LedgerSectionName = Literal[
    "frame",
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


def pinned_operational_spec(ctx: RunContext[LeadDeps]) -> str | None:
    """The in-progress Operational Spec FRAME produces — the Lead reads this to
    decide BUILD readiness."""
    spec = ctx.deps.state.operational_spec
    if spec is None:
        return "## Operational Spec\nNot framed yet. Call ``frame_problem``."
    lines = [
        "## Operational Spec",
        f"- goal: {spec.interpreted_goal or spec.goal}",
        f"- ready_to_build: {spec.ready_to_build}",
    ]
    for c in spec.criteria:
        slots = [s.param_name for s in c.open_params]
        line = f"  - [{c.id}] {c.text[:60]} -> {c.search_name or '(UNBOUND)'}"
        if slots:
            line += f" | open: {slots}"
        lines.append(line)
    if spec.dropped:
        lines.append("  dropped: " + "; ".join(d.text for d in spec.dropped))
    return "\n".join(lines)


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

    Populate ``explicit_constraints`` with one typed Constraint for every
    requirement the user STATES in this message — data type ("RNA-Seq
    only"), statistical threshold ("adjusted p <= 0.05"), fold change,
    comparator ("female vs male"), organism, record type. Capture their
    exact stated value. These override scoping's provisional assumptions
    for the same dimension, so a clarification answer like "RNA-Seq only,
    hard requirement" lands here even when scoping earlier assumed
    otherwise. Leave empty if the user states no concrete requirement.

    Set ``hard=True`` for non-negotiable requirements ("only", "must",
    "required", "do not use X"); set ``hard=False`` when the user states a
    PREFERENCE with an acceptable fallback ("RNA-Seq preferred, microarray
    fallback ok", "ideally X but Y is fine"). A soft constraint is surfaced
    but never blocks the turn if substituted.
    """
    ctx.deps.intent = intent
    return intent


def get_live_strategy_state(ctx: RunContext[LeadDeps]) -> LiveStrategyState:
    """Read the strategy as it exists RIGHT NOW, bypassing the Ledger's cache.

    The Ledger's build counts describe the last build this conversation ran.
    The user can change the strategy between turns (graph editor, WDK web
    UI), which leaves those counts wrong. Call this before stating any
    result count, parameter value, or step list as current fact — and always
    when the Ledger shows a STALE marker or the user asks what the strategy
    does "now".
    """
    return read_live_state(ctx.deps.runtime.strategy_session)


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
    here so you can run (or re-run) ``frame_problem`` with them as hard
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
            "Now run frame_problem honoring these as hard constraints."
        ),
    )


_consult_user_tool: Tool[LeadDeps] = Tool(
    consult_user,
    requires_approval=True,
)


lead_agent: Agent[LeadDeps, LeadResponse | DeferredToolRequests] = Agent(
    "openai:gpt-5.6-luna",
    output_type=[LeadResponse, DeferredToolRequests],
    deps_type=LeadDeps,
    instructions=LEAD_INSTRUCTIONS,
    tools=[
        Tool(classify_user_intent),
        Tool(read_ledger_section),
        Tool(get_live_strategy_state),
        Tool(frame_problem),
        Tool(build_strategy),
        Tool(recover_failed_steps),
        Tool(verify_strategy),
        Tool(compare_search_variants),
        Tool(build_control_set),
        Tool(list_control_sets),
        Tool(import_control_ids_from_gene_set),
        Tool(import_control_ids_from_strategy),
        Tool(compare_variants_scored),
        _consult_user_tool,
    ],
    capabilities=[
        Thinking(effort="medium"),
        *(ProcessHistory[LeadDeps](p) for p in PHASE_HISTORY_PROCESSORS),
    ],
    retries=3,
    description="The user's voice — orchestrates sub-agents via the Ledger",
    name="lead",
    defer_model_check=True,
)


for _fn in (
    pinned_user_prompt,
    pinned_user_intent,
    pinned_operational_spec,
    pinned_ledger_summary,
):
    lead_agent.instructions(_fn)
