"""Experiment wizard AI assistant — prompt construction and orchestration.

Builds step-specific system prompts, creates a lightweight
:class:`ExperimentAssistantAgent`, and streams its response.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

from kani import ChatMessage, ChatRole

from veupath_chatbot.ai.agents.factory import create_engine
from veupath_chatbot.ai.experiment_assistant import ExperimentAssistantAgent
from veupath_chatbot.ai.models.catalog import ModelProvider, ReasoningEffort
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.streaming import stream_chat

WizardStep = Literal["search", "parameters", "controls", "run"]

_BASE_PERSONA = """\
You are a scientific research assistant embedded in the VEuPathDB Experiment Lab wizard.
Your role is to help virologists and bioinformaticians configure experiments efficiently.
Be concise and actionable. When suggesting values, be specific — quote exact IDs, names,
and parameter values the user can directly use. Cite sources when using literature or web results."""

_STEP_PROMPTS: dict[WizardStep, str] = {
    "search": """\
{persona}

## Current step: Search Selection

The user needs to choose a VEuPathDB search (question) to base their experiment on.
Help them by:
1. Understanding their research question / biological goal.
2. Using literature_search and web_search to gather relevant biological context.
3. Using search_for_searches and list_searches to find matching WDK searches.
4. Explaining what each recommended search does and why it fits their goal.

The user is working on site "{site_id}".
{context_block}""",
    "parameters": """\
{persona}

## Current step: Parameter Configuration

The user has selected a search and needs to configure its parameters.
Help them by:
1. Understanding what each parameter controls.
2. Using web_search and literature_search to advise on appropriate values for their research goal.
3. Suggesting specific parameter values they can use.

The user is working on site "{site_id}".
{context_block}""",
    "controls": """\
{persona}

## Current step: Control Gene Selection

The user needs positive controls (genes expected in results) and negative controls
(genes NOT expected). Help them by:
1. Using literature_search to find published positive/negative control genes for their research area.
2. Using lookup_genes to resolve gene names/symbols to VEuPathDB gene IDs.
3. Suggesting specific gene IDs the user can add to their controls.

When suggesting genes, always provide the VEuPathDB gene ID (e.g. PF3D7_1222600)
so the user can directly add it.

The user is working on site "{site_id}".
{context_block}""",
    "run": """\
{persona}

## Current step: Run Configuration

The user is finalizing experiment settings (name, cross-validation, enrichment analyses).
Help them by:
1. Advising whether cross-validation is appropriate given their control set size.
2. Recommending which enrichment analyses (GO, pathway, word) make sense for their search.
3. Explaining what each option does in plain terms.

The user is working on site "{site_id}".
{context_block}""",
}


def _build_context_block(context: JSONObject) -> str:
    """Format wizard context into a readable block for the system prompt."""
    parts: list[str] = []
    record_type = context.get("recordType")
    if record_type:
        parts.append(f"Record type: {record_type}")
    search_name = context.get("searchName")
    if search_name:
        parts.append(f"Selected search: {search_name}")
    params = context.get("parameters")
    if isinstance(params, dict) and params:
        non_empty = {k: v for k, v in params.items() if v}
        if non_empty:
            parts.append(f"Parameters: {json.dumps(non_empty, indent=2)}")
    pos = context.get("positiveControls")
    if isinstance(pos, list) and pos:
        parts.append(
            f"Positive controls ({len(pos)}): {', '.join(str(g) for g in pos[:20])}"
            + (" ..." if len(pos) > 20 else "")
        )
    neg = context.get("negativeControls")
    if isinstance(neg, list) and neg:
        parts.append(
            f"Negative controls ({len(neg)}): {', '.join(str(g) for g in neg[:20])}"
            + (" ..." if len(neg) > 20 else "")
        )
    if not parts:
        return ""
    return "\n## Wizard context\n" + "\n".join(f"- {p}" for p in parts)


def build_system_prompt(
    step: WizardStep,
    site_id: str,
    context: JSONObject,
) -> str:
    """Build the step-specific system prompt with injected context.

    :param step: Current wizard step.
    :param site_id: VEuPathDB site identifier.
    :param context: Wizard state (search, params, controls, etc.).
    :returns: Formatted system prompt string.
    """
    template = _STEP_PROMPTS[step]
    context_block = _build_context_block(context)
    return template.format(
        persona=_BASE_PERSONA,
        site_id=site_id,
        context_block=context_block,
    )


def _build_chat_history(history: list[JSONObject]) -> list[ChatMessage]:
    """Convert raw message dicts from the frontend into Kani ChatMessages."""
    messages: list[ChatMessage] = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        role_raw = msg.get("role")
        content_raw = msg.get("content")
        if not isinstance(role_raw, str) or not isinstance(content_raw, str):
            continue
        if role_raw == "user":
            messages.append(ChatMessage(role=ChatRole.USER, content=content_raw))
        elif role_raw == "assistant":
            messages.append(ChatMessage(role=ChatRole.ASSISTANT, content=content_raw))
    return messages


async def run_assistant(
    site_id: str,
    step: WizardStep,
    message: str,
    context: JSONObject,
    history: list[JSONObject] | None = None,
    model_override: str | None = None,
    provider_override: ModelProvider | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> AsyncIterator[JSONObject]:
    """Create an experiment assistant and stream its response.

    :param site_id: VEuPathDB site identifier.
    :param step: Current wizard step.
    :param message: User message.
    :param context: Wizard state context.
    :param history: Previous conversation messages.
    :param model_override: Model catalog ID override (default: ``openai/gpt-4o-mini``).
    :param provider_override: Provider override.
    :param reasoning_effort: Reasoning effort override.
    :returns: Async iterator of SSE-compatible event dicts.
    """
    effective_model = model_override or "openai/gpt-4o-mini"
    engine = create_engine(
        model_override=effective_model,
        provider_override=provider_override,
        reasoning_effort=reasoning_effort,
    )

    system_prompt = build_system_prompt(step, site_id, context)
    chat_history = _build_chat_history(history or [])

    agent = ExperimentAssistantAgent(
        engine=engine,
        site_id=site_id,
        system_prompt=system_prompt,
        chat_history=chat_history,
    )

    async for event in stream_chat(agent, message):
        yield event
