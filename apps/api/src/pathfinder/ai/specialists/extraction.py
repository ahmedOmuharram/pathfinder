"""Targeted LLM extraction for specialist context slots.

Two small pydantic-ai agents called once on specialist entry — one to extract
the user's success criteria for /validate, one to extract biological focus
for /research. Both tolerate empty / unhelpful inputs by returning empty
defaults; the specialist's first turn can ask the user to clarify.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)

from pathfinder.ai.specialists.types import BiologicalFocus, TurnExcerpt

ExtractionFailure = (
    AgentRunError,
    UnexpectedModelBehavior,
    ModelHTTPError,
    UsageLimitExceeded,
)


def _render_excerpts(excerpts: list[TurnExcerpt]) -> str:
    if not excerpts:
        return "(no recent turns)"
    lines: list[str] = []
    for ex in excerpts:
        prefix = "USER" if ex.role == "user" else "ASSISTANT"
        suffix = (
            f" [{ex.tool_call_count} tool calls]"
            if ex.tool_call_count > 0
            else ""
        )
        lines.append(f"{prefix}{suffix}: {ex.text}")
    return "\n".join(lines)


_CRITERIA_AGENT: Agent[None, str] = Agent(
    output_type=str,
    system_prompt=(
        "You extract the user's success criteria from a conversation about "
        "building a research strategy. Output ONE concise sentence stating "
        "what the user wants the strategy to achieve. If the conversation "
        "does not contain enough information to infer success criteria, "
        "output an empty string."
    ),
    instructions=(
        "Be specific to what the user actually said. Do not invent goals "
        "the user did not state. Prefer the user's own phrasing."
    ),
)


_FOCUS_AGENT: Agent[None, BiologicalFocus] = Agent(
    output_type=BiologicalFocus,
    system_prompt=(
        "You extract the biological focus from a research question and "
        "recent conversation context. Identify the organism, gene family, "
        "and pathway when present. Leave fields null when the input does "
        "not clearly state them — do not guess."
    ),
)


async def extract_success_criteria(
    *, recent_turns: list[TurnExcerpt], model_id: str | None = None,
) -> str:
    prompt = (
        "Recent conversation turns:\n\n"
        f"{_render_excerpts(recent_turns)}\n\n"
        "Output the user's success criteria (one sentence) or empty."
    )
    try:
        result = await _CRITERIA_AGENT.run(prompt, model=model_id)
    except ExtractionFailure:
        return ""
    return result.output.strip()


async def extract_biological_focus(
    *,
    research_question: str,
    recent_turns: list[TurnExcerpt],
    model_id: str | None = None,
) -> BiologicalFocus | None:
    prompt = (
        f"Research question: {research_question or '(none)'}\n\n"
        f"Recent turns:\n{_render_excerpts(recent_turns)}\n\n"
        "Extract organism / gene family / pathway / other. Leave null "
        "when not stated."
    )
    try:
        result = await _FOCUS_AGENT.run(prompt, model=model_id)
    except ExtractionFailure:
        return None
    focus = result.output
    if (
        focus.organism is None
        and focus.gene_family is None
        and focus.pathway is None
        and focus.other is None
    ):
        return None
    return focus
