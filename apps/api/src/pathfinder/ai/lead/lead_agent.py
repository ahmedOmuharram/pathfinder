"""The Lead agent, which owns the user-facing voice and calls the sub-agent tools.

The Lead reads the typed ledger after each call and decides the next tool. A phase is
a tool the Lead invokes, not a node in a fixed graph.
"""

from __future__ import annotations

from typing import Literal

from assistant_core.graph.tool_summary import with_summary
from assistant_core.graph.turn_state import (
    ConsultQuestion,
    UserQuestionAnswer,
)
from assistant_core.memory.schemas import MemoryKind
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field
from pydantic_ai import Agent, DeferredToolRequests, RunContext, Tool
from pydantic_ai.capabilities import PrepareTools, ProcessHistory, Thinking
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.dispatch_context import agent_deps_for
from pathfinder.ai.lead.edit_dispatch import edit_strategy
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.intent_gate import hide_building_tools
from pathfinder.ai.lead.live_state import LiveStrategyState, read_live_state
from pathfinder.ai.lead.sub_agent_dispatch import (
    build_strategy,
    frame_problem,
    recover_failed_steps,
    verify_strategy,
)
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.tools.standalone import conversation, memory_tools, research
from pathfinder.ai.tools.standalone._conversation_models import ClearStrategyResult
from pathfinder.ai.tools.standalone.control_sets import (
    build_control_set,
    import_control_ids_from_gene_set,
    import_control_ids_from_strategy,
    list_control_sets,
)
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.ai.tools.standalone.variant_comparison import compare_search_variants
from pathfinder.ai.tools.toolsets import eda
from pathfinder.integrations.veupathdb.factory import get_strategy_api
from pathfinder.services.research.processing import LiteratureSearchResponse
from pathfinder.services.research.web_search import WebSearchResponse

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
    (``complete`` - typically after a successful verification).
    """

    prose: str = Field(
        max_length=4000,
        description=(
            "User-facing reply for this turn. Plain markdown. Do NOT "
            "include sub-agent log noise - synthesize from the Ledger."
        ),
    )
    next_state: LeadTurnState = "await_user"


LeadAgent = Agent[LeadDeps, LeadResponse | DeferredToolRequests]


def pinned_ledger_summary(ctx: RunContext[LeadDeps]) -> str:
    """Builds the compact ledger summary. It is derived on each render."""
    ledger = derive_ledger(ctx.deps.state, ctx.deps.intent)
    return ledger.render_summary()


def pinned_operational_spec(ctx: RunContext[LeadDeps]) -> str | None:
    """Renders the operational spec, which the Lead reads to decide build readiness."""
    spec = ctx.deps.state.domain.operational_spec
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
) -> ToolReturn[UserIntent]:
    """Classify the user's intent for this turn. Call this exactly once,
    before any other sub-agent call.

    Construct a ``UserIntent`` with: ``raw_text`` (the user's literal
    message), ``classification`` (one of the IntentClassification enum
    values), ``inferred_goal`` (your one-sentence paraphrase),
    ``is_differential`` and ``differential_sides`` when the user is
    asking a comparison question, and any referenced step/strategy IDs.

    Populate ``explicit_constraints`` with one typed Constraint for every
    requirement the user STATES in this message - data type ("RNA-Seq
    only"), statistical threshold ("adjusted p <= 0.05"), fold change,
    comparator ("female vs male"), organism, record type, and percentile
    for a stated share ("top 10% expressed", "bottom quartile"), whose
    requested value carries the share and the direction. Capture their
    exact stated value. These override scoping's provisional assumptions
    for the same dimension, so a clarification answer like "RNA-Seq only,
    hard requirement" lands here even when scoping earlier assumed
    otherwise. Leave empty if the user states no concrete requirement.

    Set ``hard=True`` for non-negotiable requirements ("only", "must",
    "required", "do not use X"); set ``hard=False`` when the user states a
    PREFERENCE with an acceptable fallback ("RNA-Seq preferred, microarray
    fallback ok", "ideally X but Y is fine"). A soft constraint is surfaced
    but never blocks the turn if substituted.

    An imperative asks for a build. "Run it", "rerun the compute", "build
    the strategy", "add those genes as a step", "create the step" - and a
    bare "yes, do it" that accepts an offer you made - are
    ``extend_strategy`` when the thread already has a strategy or an open
    analysis, ``new_strategy`` when it has neither, and
    ``clarification_response`` when they answer a question you asked. A
    retry after a failed task is the same request again, so it keeps the
    classification that request had. None of them is a
    ``follow_up_question``: that value is for a message that asks you to
    EXPLAIN something and asks for no change to the data.

    Two classifications ask for no strategy at all:

    - ``context_statement``: the message states what the user works on and
      asks for nothing. No imperative, no question about the data. Example:
      "I'm investigating virulence factors in Leishmania major".
    - ``memory_request``: the message asks you to keep something for later.
      Example: "Please remember for future sessions: I always work with
      P. falciparum 3D7 and I prefer the Su et al. strand-specific dataset."

    Both are answered in prose, and ``memory_request`` with one ``remember``
    call per thing to keep. Neither is a request to build.
    """
    ctx.deps.intent = intent
    ctx.deps.state.domain.record_intent(
        intent,
        request_text=ctx.deps.state.user_prompt,
    )
    return with_summary(
        intent,
        f"Intent: {intent.classification.value}",
        ctx=ctx,
    )


async def remember(
    ctx: RunContext[LeadDeps],
    kind: MemoryKind,
    name: str,
    summary: str,
    content: dict[str, object],
    tags: list[str] | None = None,
) -> ToolReturn[str]:
    """Store one thing the user asked you to keep for future sessions.

    Use it for a stated preference (a default organism, a preferred dataset)
    and for a fact they taught you. One call per thing remembered. Storing a
    preference is the whole answer to that request: do not build a strategy to
    "validate" it.
    """
    inner: RunContext[AgentDeps] = RunContext(
        deps=agent_deps_for(ctx.deps),
        model=ctx.model,
        usage=ctx.usage,
        tool_call_id=ctx.tool_call_id,
    )
    return await memory_tools.remember(
        inner,
        kind=kind,
        name=name,
        summary=summary,
        content=content,
        tags=tags,
    )


async def get_live_strategy_state(
    ctx: RunContext[LeadDeps],
) -> ToolReturn[LiveStrategyState]:
    """Read the strategy as it exists RIGHT NOW, bypassing the Ledger's cache.

    The Ledger's build counts describe the last build this conversation ran.
    The user can change the strategy between turns (graph editor, VEuPathDB
    web UI), which leaves those counts wrong. Call this before stating any
    result count, parameter value, or step list as current fact - and always
    when the Ledger shows a STALE marker or the user asks what the strategy
    does "now".

    Every count comes from the site. An ``estimatedSize`` or ``rootCount`` of
    null is UNKNOWN, never zero: say the count is not available for that step
    rather than reporting a number from an earlier turn. Describe a step from
    its ``parameters``, which are the values stored on it; its name can still
    describe the value it was built with.
    """
    live = await read_live_state(
        ctx.deps.runtime.strategy_session,
        get_strategy_api(ctx.deps.runtime.site_id),
    )
    if not live.step_count:
        return with_summary(live, "No strategy yet", ctx=ctx, status="empty")
    genes = live.root_count
    if genes is None:
        return with_summary(
            live,
            f"{live.step_count} steps, count not available",
            ctx=ctx,
            status="warn",
        )
    return with_summary(
        live,
        f"{live.step_count} steps, {genes:,} genes",
        ctx=ctx,
        status="ok" if genes else "empty",
    )


async def clear_strategy(
    ctx: RunContext[LeadDeps],
    *,
    confirm: bool,
) -> ToolReturn[ClearStrategyResult]:
    """Throw the whole strategy away so the user can start over.

    This is the ONLY deliberate destructive path. Use it when the user asks to
    scrap the strategy and begin again, and never as a way around
    ``build_strategy``'s refusal on a thread that already has one: a request
    that changes what the strategy asks is ``edit_strategy``.

    Every step goes, on this thread and on VEuPathDB, and the strategy's
    provenance goes with them. The user approves the call before it runs, so
    do not also ask in prose. After it returns, frame and build afresh.

    ``confirm`` must be true; the call is refused otherwise.
    """
    inner: RunContext[AgentDeps] = RunContext(
        deps=agent_deps_for(ctx.deps),
        model=ctx.model,
        usage=ctx.usage,
        tool_call_id=ctx.tool_call_id,
    )
    return await conversation.clear_strategy(inner, confirm=confirm)


async def web_search(
    ctx: RunContext[LeadDeps],
    query: str,
    limit: int = 5,
) -> ToolReturn[WebSearchResponse]:
    """Search the web and return results with citations.

    Use it to ground a claim, check a name, or answer a question the catalog
    cannot - it builds nothing and is safe in any turn.

    Args:
        ctx: Agent run context.
        query: Web search query.
        limit: Max number of results (1-10).
    """
    inner: RunContext[AgentDeps] = RunContext(
        deps=agent_deps_for(ctx.deps),
        model=ctx.model,
        usage=ctx.usage,
        tool_call_id=ctx.tool_call_id,
    )
    return await research.web_search(inner, query, limit=limit)


async def literature_search(
    ctx: RunContext[LeadDeps],
    query: str,
    limit: int = 8,
) -> ToolReturn[LiteratureSearchResponse]:
    """Search scientific literature and return results with citations.

    Use it for the biology behind a request - a gene's role, a method's
    precedent, a threshold's convention - before or after building.

    Args:
        ctx: Agent run context.
        query: Literature search query.
        limit: Max number of results (1-25).
    """
    inner: RunContext[AgentDeps] = RunContext(
        deps=agent_deps_for(ctx.deps),
        model=ctx.model,
        usage=ctx.usage,
        tool_call_id=ctx.tool_call_id,
    )
    return await research.literature_search(inner, query, limit=limit)


def read_ledger_section(
    ctx: RunContext[LeadDeps],
    section: LedgerSectionName,
) -> ToolReturn[str]:
    """Return the full detail of one Ledger section.

    The pinned summary already shows counts and derived booleans; use
    this when you need step-level detail (failed step IDs, open slot
    questions, fit-report rationales) before deciding the next move.
    """
    ledger = derive_ledger(ctx.deps.state, ctx.deps.intent)
    return with_summary(
        ledger.render_section(section),
        f"Read {section}",
        ctx=ctx,
    )


def _format_answers(answers: list[UserQuestionAnswer]) -> str:
    parts: list[str] = []
    for a in answers:
        chosen = ", ".join(a.chosen_labels) if a.chosen_labels else "(free text)"
        line = f'"{a.prompt}" -> {chosen}'
        if a.note:
            line += f" - note: {a.note}"
        parts.append(line)
    return "; ".join(parts)


async def consult_user(
    ctx: RunContext[LeadDeps],
    questions: list[ConsultQuestion],
) -> ToolReturn[list[UserQuestionAnswer]]:
    """Ask the user design questions that SHAPE the investigation, before a
    plan is built. Use this whenever a real fork exists - which searches to
    combine, a threshold that changes the steps, whether to add an arm -
    instead of guessing or bundling the choice into plan approval.

    This pauses the turn: the user answers each question in a carousel
    (options + optional free-text note). Their answers are returned to you
    here so you can run (or re-run) ``frame_problem`` with them as hard
    constraints. Ask only the few questions that genuinely change the
    answer; pick sensible defaults for everything else and state your
    assumptions in prose. Do NOT ask "submit or request changes?" - the
    approval card already offers both. Background for a question goes in
    that question's ``context``; the call itself takes only ``questions``.
    """
    state = ctx.deps.state
    pending = state.pending_approval
    answers = (
        list(state.user_question_answers.get(pending.tool_call_id, []))
        if pending is not None
        else []
    )
    asked = with_summary(
        answers,
        f"{len(questions)} questions asked",
        ctx=ctx,
    )
    asked.content = (
        f"Presented {len(questions)} question(s); awaiting the user's answers."
        if not answers
        else (
            f"The user answered your questions: {_format_answers(answers)}. "
            "Now run frame_problem honoring these as hard constraints."
        )
    )
    return asked


LEAD_MODEL = "openai:gpt-5.6-luna"


def build_lead_agent() -> LeadAgent:
    """A Lead agent for one turn.

    Each turn gets its own instance, so a per-turn model override never
    reaches another turn.
    """
    agent: LeadAgent = Agent(
        LEAD_MODEL,
        output_type=[LeadResponse, DeferredToolRequests],
        deps_type=LeadDeps,
        instructions=LEAD_INSTRUCTIONS,
        tools=[
            Tool(classify_user_intent),
            Tool(remember),
            Tool(web_search),
            Tool(literature_search),
            Tool(read_ledger_section),
            Tool(get_live_strategy_state),
            Tool(frame_problem),
            Tool(edit_strategy),
            Tool(build_strategy),
            Tool(recover_failed_steps),
            Tool(verify_strategy),
            Tool(compare_search_variants),
            Tool(build_control_set),
            Tool(list_control_sets),
            Tool(import_control_ids_from_gene_set),
            Tool(import_control_ids_from_strategy),
            Tool(compare_variants_scored),
            Tool(clear_strategy, requires_approval=True),
            Tool(consult_user, requires_approval=True),
        ],
        toolsets=[eda.build_toolset()],
        capabilities=[
            Thinking(effort="medium"),
            PrepareTools[LeadDeps](hide_building_tools),
            *(ProcessHistory[LeadDeps](p) for p in PHASE_HISTORY_PROCESSORS),
        ],
        retries=3,
        description="The user's voice - orchestrates sub-agents via the Ledger",
        name="lead",
        defer_model_check=True,
    )
    for fn in (
        pinned_user_prompt,
        pinned_user_intent,
        pinned_operational_spec,
        pinned_ledger_summary,
    ):
        agent.instructions(fn)
    return agent
