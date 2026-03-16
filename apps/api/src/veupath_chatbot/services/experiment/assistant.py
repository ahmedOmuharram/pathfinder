"""Experiment wizard AI assistant — prompt construction and orchestration.

Builds step-specific system prompts, creates a lightweight
experiment assistant agent, and streams its response.

AI-layer dependencies (engine factory, agent classes) are injected at
startup via :func:`configure` so that the services layer never imports
from ``veupath_chatbot.ai``.
"""

import json
from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from kani import ChatMessage, ChatRole, Kani
from kani.engines.base import BaseEngine

from veupath_chatbot.platform.types import JSONObject, ModelProvider, ReasoningEffort
from veupath_chatbot.services.chat.streaming import stream_chat
from veupath_chatbot.services.experiment.types import WizardStep

# ── Injected AI-layer dependencies ──────────────────────────────────
# Set once at startup via configure().

_create_engine: Callable[..., BaseEngine] | None = None
_experiment_agent_cls: type[Kani] | None = None


def configure(
    *,
    create_engine_fn: Callable[..., BaseEngine],
    experiment_agent_cls: type[Kani],
) -> None:
    """Wire AI-layer implementations into the experiment assistant.

    Called once at application startup from the composition root.
    """
    global _create_engine, _experiment_agent_cls
    _create_engine = create_engine_fn
    _experiment_agent_cls = experiment_agent_cls


_BASE_PERSONA = """\
You are a scientific research assistant embedded in the VEuPathDB Experiment Lab wizard.
Your role is to help virologists and bioinformaticians configure experiments efficiently.
Be concise and actionable. When suggesting values, be specific — quote exact IDs, names,
and parameter values the user can directly use. Cite sources when using literature or web results."""

# Step prompt templates are loaded from .md files in ai/prompts/experiment/.
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "ai" / "prompts" / "experiment"

_STEP_FILES: dict[WizardStep, str] = {
    "search": "search.md",
    "parameters": "parameters.md",
    "controls": "controls.md",
    "run": "run.md",
    "analysis": "analysis.md",
}


@lru_cache
def _load_step_prompt(step: WizardStep) -> str:
    """Load a step prompt template from its .md file."""
    filename = _STEP_FILES[step]
    return (_PROMPTS_DIR / filename).read_text()


def _build_context_block(context: JSONObject) -> str:
    """Format wizard context into a readable block for the system prompt."""
    parts: list[str] = []
    record_type = context.get("recordType")
    if record_type:
        parts.append(f"Record type: {record_type}")
    search_name = context.get("searchName")
    if search_name:
        parts.append(f"Selected search: {search_name}")
    mode = context.get("mode")
    if isinstance(mode, str) and mode:
        parts.append(f"Experiment mode: {mode}")
    strategy_summary = context.get("strategySummary")
    if isinstance(strategy_summary, str) and strategy_summary:
        parts.append(f"Strategy: {strategy_summary}")
    params = context.get("parameters")
    if isinstance(params, dict) and params:
        non_empty = {k: v for k, v in params.items() if v}
        if non_empty:
            parts.append(f"Parameters: {json.dumps(non_empty, indent=2)}")
    for label, key in (
        ("Positive", "positiveControls"),
        ("Negative", "negativeControls"),
    ):
        controls = context.get(key)
        if isinstance(controls, list) and controls:
            preview = ", ".join(str(g) for g in controls[:20])
            suffix = " ..." if len(controls) > 20 else ""
            parts.append(f"{label} controls ({len(controls)}): {preview}{suffix}")
    # Results: classification metrics (for results/analysis steps)
    metrics = context.get("metrics")
    if isinstance(metrics, dict) and metrics:
        m_parts = []
        for key in (
            "sensitivity",
            "specificity",
            "precision",
            "f1Score",
            "mcc",
            "balancedAccuracy",
            "totalResults",
        ):
            val = metrics.get(key)
            if val is not None:
                m_parts.append(f"{key}: {val}")
        if m_parts:
            parts.append("Classification metrics: " + ", ".join(m_parts))
    cm = context.get("confusionMatrix")
    if isinstance(cm, dict) and cm:
        tp = cm.get("TP", cm.get("truePositives"))
        fp = cm.get("FP", cm.get("falsePositives"))
        fn = cm.get("FN", cm.get("falseNegatives"))
        tn = cm.get("TN", cm.get("trueNegatives"))
        if any(v is not None for v in (tp, fp, fn, tn)):
            parts.append(f"Confusion matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}")
    enrichment = context.get("enrichmentSummary")
    if isinstance(enrichment, str) and enrichment.strip():
        parts.append(f"Enrichment findings:\n{enrichment}")
    gene_lists = context.get("geneListsSummary")
    if isinstance(gene_lists, str) and gene_lists.strip():
        parts.append(f"Gene lists (sample):\n{gene_lists}")
    cv = context.get("crossValidation")
    if isinstance(cv, dict) and cv:
        cv_parts = []
        if cv.get("overfittingLevel") is not None:
            cv_parts.append(f"overfitting: {cv['overfittingLevel']}")
        if cv.get("overfittingScore") is not None:
            cv_parts.append(f"score={cv['overfittingScore']}")
        if cv.get("meanF1") is not None:
            cv_parts.append(f"mean F1={cv['meanF1']}")
        if cv_parts:
            parts.append("Cross-validation: " + ", ".join(cv_parts))
    exp_id = context.get("experimentId")
    if isinstance(exp_id, str) and exp_id:
        parts.append(f"Experiment ID: {exp_id}")
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
    template = _load_step_prompt(step)
    context_block = _build_context_block(context)
    experiment_id = (
        str(context.get("experimentId", "")) if isinstance(context, dict) else ""
    )
    fmt_kwargs = {
        "persona": _BASE_PERSONA,
        "site_id": site_id,
        "context_block": context_block,
        "experiment_id": experiment_id,
    }
    import string

    formatter = string.Formatter()
    used_keys = {
        field_name
        for _, field_name, _, _ in formatter.parse(template)
        if field_name is not None
    }
    return template.format(**{k: v for k, v in fmt_kwargs.items() if k in used_keys})


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
    :param model_override: Model catalog ID override (default: ``openai/gpt-4.1-nano``).
    :param provider_override: Provider override.
    :param reasoning_effort: Reasoning effort override.
    :returns: Async iterator of SSE-compatible event dicts.
    """
    if _create_engine is None or _experiment_agent_cls is None:
        raise RuntimeError(
            "Experiment assistant not configured. "
            "Call services.experiment.assistant.configure() at startup."
        )

    effective_model = model_override or "openai/gpt-4.1-nano"
    engine = _create_engine(
        model_override=effective_model,
        provider_override=provider_override,
        reasoning_effort=reasoning_effort,
    )

    system_prompt = build_system_prompt(step, site_id, context)
    chat_history = _build_chat_history(history or [])

    agent: Kani
    if step == "analysis":
        from veupath_chatbot.services.experiment.ai_analysis_tools import (
            ExperimentAnalysisAgent,
        )

        experiment_id = (
            str(context.get("experimentId", "")) if isinstance(context, dict) else ""
        )
        agent = ExperimentAnalysisAgent(
            engine=engine,
            site_id=site_id,
            experiment_id=experiment_id,
            system_prompt=system_prompt,
            chat_history=chat_history,
        )
    else:
        # Dynamic dispatch: the actual class (ExperimentAssistantAgent)
        # accepts site_id, but the static type is type[Kani].
        agent = cast(Any, _experiment_agent_cls)(
            engine=engine,
            site_id=site_id,
            system_prompt=system_prompt,
            chat_history=chat_history,
        )

    async for event in stream_chat(agent, message, model_id=effective_model):
        yield event
