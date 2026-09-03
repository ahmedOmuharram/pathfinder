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
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.agents._instructions import (
    pinned_run_budget,
    pinned_user_memories,
)
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.dispatch_context import inner_context
from pathfinder.ai.lead.dispatch_messages import (
    blamed_the_site_message,
    unverified_build_message,
)
from pathfinder.ai.lead.edit_dispatch import edit_strategy
from pathfinder.ai.lead.guarantees import machine_guarantees_pin
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.intent_gate import apply_tool_preconditions
from pathfinder.ai.lead.lead_pins import (
    pinned_ledger_summary,
    pinned_operational_spec,
    pinned_turn_briefing,
    pinned_user_intent,
    pinned_user_prompt,
)
from pathfinder.ai.lead.ledger import blamed_the_site
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
from pathfinder.ai.tools.standalone._research_models import (
    LiteratureSearchOut,
    WebSearchOut,
)
from pathfinder.ai.tools.standalone.control_sets import (
    build_control_set,
    import_control_ids_from_gene_set,
    import_control_ids_from_strategy,
    list_control_sets,
)
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.ai.tools.standalone.variant_comparison import compare_search_variants
from pathfinder.ai.tools.toolsets import eda
from pathfinder.domain.strategy.constraints import (
    CombinationRequest,
    Constraint,
    ConstraintKind,
    ConstraintSource,
)
from pathfinder.integrations.veupathdb.factory import get_strategy_api

LeadTurnState = Literal["await_user", "complete"]
LedgerSectionName = Literal["frame", "build", "verification"]


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

    When the user says HOW their evidence lines combine - "A OR B",
    "either mass spec or DeRisi expression", "combine the two domain
    searches with a union", "both filters must hold" - add one constraint
    of kind "combination". Its requested value is that combination in the
    canonical form "<term> OR <term>" (or AND), with one term per line of
    evidence, written in the user's own words for it. Two terms minimum,
    one operator only: a request that mixes OR and AND is two
    constraints, one per group. This is the only machine-checkable record
    of the boolean shape they asked for, so a stated combination that
    never lands here is a strategy that can silently answer the other
    question.

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
    ctx.deps.state.turn_markers.intent_classified = True
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
    inner = inner_context(ctx)
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

    Every step goes from this thread, and the next build creates a strategy of
    its own on VEuPathDB instead of reusing the one that stood here. The
    cleared state appends a revision, so a revert restores what this call
    cleared. The user approves the call before it runs, so do not also ask in
    prose. After it returns, frame and build afresh.

    ``confirm`` must be true; the call is refused otherwise.
    """
    inner = inner_context(ctx)
    return await conversation.clear_strategy(inner, confirm=confirm)


async def web_search(
    ctx: RunContext[LeadDeps],
    query: str,
    limit: int = 5,
) -> ToolReturn[WebSearchOut]:
    """Search the web and return results with citations.

    Use it to ground a claim, check a name, or answer a question the catalog
    cannot - it builds nothing and is safe in any turn.

    Args:
        ctx: Agent run context.
        query: Web search query.
        limit: Max number of results (1-10).
    """
    inner = inner_context(ctx)
    return await research.web_search(inner, query, limit=limit)


async def literature_search(
    ctx: RunContext[LeadDeps],
    query: str,
    limit: int = 8,
) -> ToolReturn[LiteratureSearchOut]:
    """Search scientific literature and return results with citations.

    Use it for the biology behind a request - a gene's role, a method's
    precedent, a threshold's convention - before or after building.

    Args:
        ctx: Agent run context.
        query: Literature search query.
        limit: Max number of results (1-25).
    """
    inner = inner_context(ctx)
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


_LABEL_LIMIT = 120


def _answer_requirements(answers: list[UserQuestionAnswer]) -> list[Constraint]:
    """The answers as requirements, one per answer that states a value.

    An answer that reads as a combination expression is typed as one, so the
    structure gate and the verification hold can check it.
    """
    requirements: list[Constraint] = []
    for answer in answers:
        stated = (
            "; ".join(answer.chosen_labels) if answer.chosen_labels else answer.note
        )
        if not stated:
            continue
        expression = next(
            (
                text
                for text in (*answer.chosen_labels, answer.note)
                if CombinationRequest.parse(text) is not None
            ),
            None,
        )
        requirements.append(
            Constraint(
                kind=(
                    ConstraintKind.OTHER
                    if expression is None
                    else ConstraintKind.COMBINATION
                ),
                requested_value=expression or stated,
                # A question carries the label. An unlabelled one falls back to
                # the answer, because a requirement is always named.
                label=answer.prompt[:_LABEL_LIMIT] or stated[:_LABEL_LIMIT],
                source=ConstraintSource.USER_EXPLICIT,
                hard=True,
            )
        )
    return requirements


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
    if answers:
        # Their answers are new requirements, so one more frame is licensed.
        state.turn_markers.framed = False
        state.domain.record_requirements(_answer_requirements(answers))
    asked.content = (
        f"Presented {len(questions)} question(s); awaiting the user's answers."
        if not answers
        else (
            f"The user answered your questions: {_format_answers(answers)}. "
            "Now run frame_problem honoring these as hard constraints."
        )
    )
    return asked


def verify_what_this_turn_built(
    ctx: RunContext[LeadDeps],
    output: LeadResponse | DeferredToolRequests,
) -> LeadResponse | DeferredToolRequests:
    """Refuse the first answer of a turn that built and never verified.

    The precondition gate offers ``verify_strategy``; a gate cannot compel the
    call. The refusal is asked once per turn, so a second answer that states
    why a check is impossible still reaches the user.
    """
    markers = ctx.deps.state.turn_markers
    if (
        not markers.built
        or markers.verified
        or markers.verification_dispatched
        or markers.verification_nudged
    ):
        return output
    markers.verification_nudged = True
    raise ModelRetry(
        unverified_build_message(ctx.deps.state.domain.last_build_outcome),
    )


def refuse_blaming_the_site(
    ctx: RunContext[LeadDeps],
    output: LeadResponse | DeferredToolRequests,
) -> LeadResponse | DeferredToolRequests:
    """Refuse a reply that attributes an internal stop to VEuPathDB.

    A pass that ran out of calls is this turn's own limit. The refusal names
    that limit, so the rewrite states it instead of asking the user to wait for
    a site that reported no failure. It is asked once per turn.
    """
    if not isinstance(output, LeadResponse) or ctx.deps.site_blame_refused:
        return output
    ledger = derive_ledger(ctx.deps.state, ctx.deps.intent)
    blame = blamed_the_site(output.prose, build=ledger.build)
    if blame is None:
        return output
    ctx.deps.site_blame_refused = True
    raise ModelRetry(blamed_the_site_message(blame, ctx.deps.last_phase_stop))


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
            PrepareTools[LeadDeps](apply_tool_preconditions),
            *(ProcessHistory[LeadDeps](p) for p in PHASE_HISTORY_PROCESSORS),
        ],
        retries=3,
        description="The user's voice - orchestrates sub-agents via the Ledger",
        name="lead",
        defer_model_check=True,
    )
    for fn in (
        pinned_user_memories,
        pinned_user_prompt,
        pinned_user_intent,
        pinned_operational_spec,
        pinned_ledger_summary,
        pinned_run_budget,
    ):
        agent.instructions(fn)
    agent.instructions(machine_guarantees_pin(agent.toolsets))
    agent.instructions(pinned_turn_briefing)
    agent.output_validator(verify_what_this_turn_built)
    agent.output_validator(refuse_blaming_the_site)
    return agent
