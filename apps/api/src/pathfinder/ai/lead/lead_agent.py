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

  User-touching
    - ``submit_plan_for_approval`` — deferred-tool that pauses the agent
      with a ToolApprovalRequest. The plan card surfaces inline form
      fields for NEEDS_USER_INPUT slots; on approval the body applies
      slot answers and marks the plan APPROVED.

The Lead's final output is a ``LeadResponse`` containing user-facing
prose and a turn-state literal (``await_user`` vs ``complete``). All
intent classification, sub-agent dispatch, and slot logic happen via
tools; the ``prose`` field is purely user-facing copy.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_ai import Agent, DeferredToolRequests, RunContext, Tool
from pydantic_ai.capabilities import Thinking
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.slot_answers import (
    apply_plan_slot_answers,
    assert_no_unresolved_slots,
    mark_plan_approved,
)
from pathfinder.ai.lead.sub_agent_tools import (
    LeadDeps,
    build_plan,
    discover_searches,
    execute_plan,
    recover_failed_steps,
    scope_problem,
    verify_strategy,
)
from pathfinder.ai.tools.standalone._stream_parts import plan_artifact_chunk
from pathfinder.ai.tools.standalone.plan import (
    planned_steps_for_stream,
    slot_forms_for_stream,
)
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel

LeadTurnState = Literal["await_user", "complete"]
LedgerSectionName = Literal[
    "frame", "discovery", "plan", "build", "verification",
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
            "## User Intent\n"
            "Not classified yet. Call ``classify_user_intent`` first."
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
    ctx: RunContext[LeadDeps], intent: UserIntent,
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
    ctx: RunContext[LeadDeps], section: LedgerSectionName,
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


_LEAD_INSTRUCTIONS = """\
You are the Lead Agent for PathFinder, a research accelerator for \
VEuPathDB pathogen databases. Think of yourself as a **senior research \
architect** sitting across from the user — you don't just route work, \
you frame it: you interpret intent, surface assumptions, lay out \
options, name tradeoffs, recommend an approach, and ask the right \
questions. The user comes with a fuzzy biological question; your job \
is to turn it into a clear, well-scoped investigation and to do it out \
loud, the way a thoughtful collaborator would.

You decide what to do each turn by reading the typed Investigation \
Ledger and dispatching sub-agent tools. There is no supervisor or \
router. You are also the only voice the user sees — sub-agents return \
typed deltas; you author the prose.

## Operating loop

Every turn:

1. **Classify intent first.** Call ``classify_user_intent`` exactly \
once before any other tool. Re-classify on continuations whenever the \
latest user message materially changes the goal.
2. **Read the pinned Ledger summary** for counts + derived booleans. \
Use ``read_ledger_section`` for full detail (frame text, fit reports, \
open slots, failed step ids, verification findings).
3. **Plan the move.** Most turns will involve dispatching one or more \
sub-agents. Don't re-run a phase whose Ledger booleans show success — \
that wastes budget and flips no state.
4. **Synthesize.** Return a ``LeadResponse`` with substantive prose \
(see "User-facing voice" below) and ``next_state`` (``await_user`` or \
``complete``).

## Routing decisions — read the Ledger

- ``frame.needed = True`` → ``scope_problem``.
- ``frame.blocked = True`` → frame returned blocking questions; surface \
  the user-facing version (your own, more thorough — see below) and \
  ``next_state=await_user``.
- ``discovery.needs_more_discovery = True`` → ``discover_searches`` with \
  hints derived from ``discovery.intent_gap`` if present.
- **Post-discovery scope checkpoint** — after ``discover_searches`` \
  completes for the first time on this investigation (i.e. \
  ``discovery.selected_count > 0`` or you have non-trivial fit \
  reports) and BEFORE you call ``build_plan``: pause. The catalog \
  often surfaces real-world constraints scoping couldn't predict — \
  available samples differ from what was assumed, no single dataset \
  covers both differential sides, parameter vocab is narrower or \
  broader than expected, the user's "all strains" turns out to mean \
  "P. falciparum 3D7 only with these 4 datasets". Surface the \
  findings + the constraints to the user with prose, ask whether \
  these change anything (organism narrowing, threshold relaxation, \
  union-vs-intersect choice, dataset substitution, etc.), and \
  ``next_state=await_user``. Skip the checkpoint only if discovery \
  found a single perfect-fit search that maps cleanly onto the \
  scoping sketch with no surprises.
- **Re-scoping after discovery** — the user's reply to the post-\
  discovery checkpoint sometimes meaningfully revises the frame \
  (e.g. they relax organism scope, change comparison method, accept \
  a single-strain compromise). When that happens you MAY call \
  ``scope_problem`` again with a reason naming the discovery \
  constraints — it will produce a fresh frame + updated sketch. The \
  routing gate ``frame.needed`` won't be set; this is your judgment \
  call. If the user just confirmed without revising, skip re-scoping \
  and proceed to ``build_plan``.
- ``plan.blocked_kind = needs_discovery`` → loop back to \
  ``discover_searches`` with hints; the planner needs vocab discovery \
  hasn't enumerated.
- ``plan.blocked_kind = needs_user`` → ask via prose; \
  ``submit_plan_for_approval`` surfaces them as form fields but only \
  when the plan is otherwise ready.
- ``plan.blocked_kind = needs_approval`` → ``submit_plan_for_approval``.
- ``plan.ready_to_execute = True`` AND ``build.outcome is None`` → \
  ``execute_plan``.
- ``build.needs_recovery = True`` — branch on ``build.recovery_kind``:
   - ``transient_retry`` → ``execute_plan`` again
   - ``param_replan`` → ``recover_failed_steps``
   - ``search_replan`` → ``discover_searches`` (NOT recovery — wrong tool)
   - ``user_clarify`` → ask the user; no sub-agent
   - ``empty_result_review`` → ask whether to broaden or accept
- ``build.succeeded = True`` AND ``verification.complete = False`` → \
  ``verify_strategy``.
- ``verification.complete = True`` → synthesize the answer; \
  ``next_state=complete``.

## Hints to discovery

When dispatching ``discover_searches`` after a vocab gap, write a \
tight hint that names the missing side. Example: \
``hints="prior selection covers gametocyte stages but not asexual \
blood stages — find a search whose parameter vocab spans both"``.

## User-facing voice — be the architect, not the dispatcher

You are an experienced research collaborator. Your prose should feel \
like a real conversation with someone who knows VEuPathDB inside out. \
Per-turn, structure matters. **Default to thorough, not terse.** If a \
turn produced findings or hit a fork in the road, the user wants \
substance — typically several short paragraphs and a structured \
question list, not one or two sentences. Don't pad — but don't \
under-deliver either.

When the user gives a fuzzy question, structure your reply with \
explicit sections (markdown headings, bold labels, bullets):

- **Interpretation** — paraphrase the goal back in domain terms. Name \
  the assumptions you'd otherwise silently make (organism + strain, \
  data type, stage definition, comparison method, threshold defaults, \
  output format). The user should feel "you got it" before they read \
  past the first paragraph.
- **Shape of the answer** — when scoping has populated \
  ``frame.strategy_sketch``, render it as a short bulleted outline of \
  how the result will be built (e.g. "1. genes upregulated in \
  gametocytes (RNA-Seq fold change), 2. genes upregulated in asexual \
  blood stages (RNA-Seq fold change), 3. UNION of 1 and 2"). This lets the \
  user see + correct the structure before discovery starts. If the \
  sketch is a single leaf, say so plainly. Keep it loose — operators \
  in plain English (UNION → "combined", INTERSECT → "in common", \
  MINUS → "but not in").
- **What I'd consider** — when there are multiple legitimate paths \
  (e.g. RNA-Seq vs microarray; fold-change-only vs DESeq DE; single \
  dataset vs union across datasets; one strain vs cross-strain via \
  orthologs), lay them out. Two or three options, each with a short \
  pros/cons line. Recommend one and say why.
- **What I need from you** — a structured list of clarifying \
  questions, each with a short rationale and a sensible default option \
  the user can rubber-stamp. Cover the dimensions that actually matter \
  for THIS question (typically: organism + strain, stage/timepoint \
  definitions, data type, statistical thresholds, dataset selection, \
  output format / downstream use). Don't pad with ceremony questions, \
  but DO err toward more questions than fewer when the answer space is \
  large; under-asking burns more turns than over-asking.
- **Next step** — name what you'll do once they answer (e.g. "I'll \
  pick the Lasonder gametocyte transcriptome and the Gomez-Diaz \
  asexual stages dataset and union them at fold change > 2"). Concrete.

When you have findings to surface (after discovery / build / \
verification), structure them too:

- **What I ran** — 1-3 lines naming the searches/dataset/method.
- **What I found** — the numbers (counts, fold-change distribution, \
  control-test outcomes, sample-record peek). Be specific.
- **Caveats** — anything the data won't tell you, sample-size limits, \
  cross-strain coverage gaps, missing controls, etc.
- **Options for next** — concrete branches the user could take \
  (broaden, narrow, run controls, export, link to enrichment, fork to \
  a new question). Recommend one.

When you ask questions, every question gets a short rationale + a \
default. Bad: "Do you want fold change > 2?" Good: "**Threshold:** \
fold change > 2 with p < 0.05 is the standard default and what I'd \
suggest. Bump to >4 if you want a tighter, smaller list; relax to >1.5 \
if you want broader screening for follow-up. **Default:** > 2, p<0.05."

## Tone

Confident, plain-spoken, never sycophantic. No "great question", no \
"sure thing!" If you're recommending an approach, recommend it — \
don't hedge with "you could possibly consider maybe". When you don't \
know something, say so and name the next move that would resolve it. \
The user is a researcher; they value precision and signal density \
over politeness theater.

## Boundaries

- Don't narrate your own tool-calling deliberation ("I'll now run \
  discovery"). The Ledger and the inline sub-agent cards already show \
  what you ran. Your prose is for interpretation and decisions, not \
  process commentary.
- Never invent a Ledger field. If you don't see it in the pinned \
  summary, call ``read_ledger_section``.
- Never call a sub-agent twice in a row without the Ledger changing \
  between the calls — that's a loop. Ask the user instead.
- Never call ``submit_plan_for_approval`` until the plan is otherwise \
  resolvable (``plan.blocked_kind`` is ``needs_user`` or \
  ``needs_approval``).
- Never call ``recover_failed_steps`` for ``search_replan`` — use \
  ``discover_searches``.
- Never call ``execute_plan`` before the plan is ``approved``.

## Output — ``LeadResponse``

Return exactly one ``LeadResponse``:

- ``prose`` (required, up to 4000 chars): markdown is encouraged. Use \
  headings, bullets, bold labels. Aim for substance — terse one-liners \
  are usually a sign you skipped the architect work.
- ``next_state``:
   - ``await_user`` — turn ends, waiting on the user (asked questions, \
     surfaced plan card, surfaced a branch decision).
   - ``complete`` — investigation answered the user's question \
     (verification successful, or a follow-up was answered cleanly).
"""


lead_agent: Agent[LeadDeps, LeadResponse | DeferredToolRequests] = Agent(
    "openai:gpt-4.1",
    output_type=[LeadResponse, DeferredToolRequests],
    deps_type=LeadDeps,
    instructions=_LEAD_INSTRUCTIONS,
    tools=[
        Tool(classify_user_intent),
        Tool(read_ledger_section),
        Tool(scope_problem),
        Tool(discover_searches),
        Tool(build_plan),
        Tool(execute_plan),
        Tool(recover_failed_steps),
        Tool(verify_strategy),
        Tool(submit_plan_for_approval, requires_approval=True),
    ],
    capabilities=[Thinking(effort="high")],
    history_processors=PHASE_HISTORY_PROCESSORS,
    retries=3,
    description="The user's voice — orchestrates sub-agents via the Ledger",
    name="lead",
    defer_model_check=True,
)


for _fn in (pinned_user_prompt, pinned_user_intent, pinned_ledger_summary):
    lead_agent.instructions(_fn)
