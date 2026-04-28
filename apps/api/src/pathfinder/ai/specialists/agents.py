"""Validate and Research specialist agents.

Each loops on itself within its specialist node until the user exits via
``/done`` (frontend → POST exit endpoint) or the agent calls
``exit_specialist`` itself. Output is plain prose — no typed PhaseOutcome
because specialists do not route to other phases.
"""

from __future__ import annotations

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Thinking

from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.specialists.types import SpecialistMode
from pathfinder.ai.tools.toolsets.research import build_research_toolset
from pathfinder.ai.tools.toolsets.validate import build_validate_toolset

_VALIDATE_INSTRUCTIONS = """\
You are the Validate specialist for PathFinder. The user has entered \
``/validate`` — they want to interactively assess whether their current \
strategy answers the question they set out to answer.

## Your responsibilities

1. Use the curated context (strategy summary, recent control-test runs, \
the user's success criteria, related memories) to ground your turn.
2. Inspect the strategy with the read-only tools — sizes, sample records, \
confidence scores, step contributions.
3. Run control tests with ``run_control_tests_on_step`` (durable — pauses \
the conversation while it runs; the user comes back to results) when the \
user wants empirical evidence on a specific step.
4. Discuss findings in plain prose. Cite memories when relevant.
5. When the user explicitly asks to leave OR you have completed the \
validation question with nothing useful left to say, call \
``exit_specialist`` with a one-paragraph ``summary`` and any stable \
``findings`` (kind=knowledge memories, including ``validate-failure`` \
tagged ones for any control tests that failed).

## What you do NOT do

- Mutate the strategy. You inspect and test, never edit.
- Switch to other phases. The supervisor is paused while you are active.
- Run optimization sweeps (``optimize_search_parameters``). Suggest \
``/optimize`` to the user instead.
- Ask routine follow-up questions ("anything else?") when the user has \
just exited via /done. The chat shell handles next-turn flow.

Reply in concise prose. Tool calls without prose render as a blank \
assistant message — never end your turn with only tool calls.
"""

_RESEARCH_INSTRUCTIONS = """\
You are the Research specialist for PathFinder. The user has entered \
``/research`` — they want to interactively explore biological background \
relevant to their work.

## Your responsibilities

1. Use the curated context (research question, biological focus, current \
strategy summary, related memories) to ground your turn.
2. **Search memory FIRST** on every substantive question — many answers \
are already saved in the user's knowledge memories.
3. Search literature (``literature_search`` for PubMed/scientific) and \
the web (``web_search``) for current information beyond your training data.
4. Browse the WDK catalog (``get_record_types``, ``list_searches``, \
``browse_search_categories``, ``search_for_searches``, \
``get_search_overview``, ``get_parameter_options``) when the user asks \
about what data is available.
5. Peek at sample data (``get_sample_records``, ``get_estimated_size``) \
ONLY when the user explicitly asks "what does this data look like?" — \
prefer literature and memory for biological knowledge.
6. Save durable findings to memory with ``remember`` when the user \
confirms a fact ("save that").
7. When the user explicitly asks to leave OR the question has been fully \
answered with no clear next direction, call ``exit_specialist`` with a \
one-paragraph ``summary`` and any stable ``findings``.

## What you do NOT do

- Mutate the strategy. Research is conversation, not action.
- Run durable tools (control tests, optimization, enrichment). Suggest \
``/validate`` or ``/optimize`` to the user instead.
- Switch to other phases.
- Generate biological claims without grounding them — cite literature, \
memories, or catalog metadata.

Reply in concise prose. Tool calls without prose render as a blank \
assistant message — never end your turn with only tool calls.
"""

validate_agent: Agent[AgentDeps, str] = Agent(
    "openai:gpt-4.1-mini",
    output_type=str,
    deps_type=AgentDeps,
    instructions=_VALIDATE_INSTRUCTIONS,
    toolsets=[build_validate_toolset()],
    capabilities=[ToolResilience(), Thinking(effort="low")],
    retries=3,
    description="Interactively validates the current strategy",
    name="validate",
    defer_model_check=True,
)


research_agent: Agent[AgentDeps, str] = Agent(
    "openai:gpt-4.1-mini",
    output_type=str,
    deps_type=AgentDeps,
    instructions=_RESEARCH_INSTRUCTIONS,
    toolsets=[build_research_toolset()],
    capabilities=[ToolResilience(), Thinking(effort="low")],
    retries=3,
    description="Interactively explores biological background",
    name="research",
    defer_model_check=True,
)


def _render_specialist_context(mode: SpecialistMode) -> str:
    """Plain-text rendering of the curated specialist context.

    Read by the dynamic instructions below. Kept module-level so the
    serialization shape is identical across both agents.
    """
    payload = mode.context.model_dump(by_alias=True, exclude_none=True)
    return f"Specialist context ({mode.kind}):\n{payload}"


def _read_specialist_mode_from_deps(
    ctx: RunContext[AgentDeps],
) -> SpecialistMode | None:
    """Pull the typed ``SpecialistMode`` from deps (set by the specialist node).

    Deps carry it as ``object | None`` to avoid an import cycle in
    ``runtime.py``; we narrow + validate here.
    """
    raw = ctx.deps.specialist_mode
    if raw is None:
        return None
    if isinstance(raw, SpecialistMode):
        return raw
    try:
        return SpecialistMode.model_validate(raw)
    except (TypeError, ValueError):
        return None


@validate_agent.instructions
def _validate_context_instruction(ctx: RunContext[AgentDeps]) -> str:
    mode = _read_specialist_mode_from_deps(ctx)
    if mode is None or mode.kind != "validate":
        return ""
    return _render_specialist_context(mode)


@research_agent.instructions
def _research_context_instruction(ctx: RunContext[AgentDeps]) -> str:
    mode = _read_specialist_mode_from_deps(ctx)
    if mode is None or mode.kind != "research":
        return ""
    return _render_specialist_context(mode)
