"""Factory helpers for constructing the agent and its engine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, cast
from uuid import UUID

from kani import ChatMessage
from kani.engines.base import BaseEngine
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.ai.model_catalog import (
    ModelProvider,
    ReasoningEffort,
    build_reasoning_hyperparams,
    get_model_entry,
)
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONArray, JSONObject

from .agent_runtime import PathfinderAgent
from .planner_runtime import PathfinderPlannerAgent

ChatMode = Literal["execute", "plan"]


# ---------------------------------------------------------------------------
# Per-provider engine constructors
# ---------------------------------------------------------------------------


def _create_openai_engine(
    *, model: str, temperature: float, top_p: float, hyperparams: JSONObject
) -> OpenAIEngine:
    settings = get_settings()
    # Some OpenAI models only support default sampling params (temperature=1, top_p=1).
    # To avoid hard failures, we omit temperature/top_p entirely for those models.
    sampling_restricted = model.startswith(("gpt-5", "o1", "o3", "o4"))
    kwargs: dict[str, object] = {}
    if not sampling_restricted:
        kwargs["temperature"] = temperature
        kwargs["top_p"] = top_p
    return OpenAIEngine(
        api_key=settings.openai_api_key,
        model=model,
        **kwargs,
        **(hyperparams or {}),
    )


def _create_anthropic_engine(
    *, model: str, temperature: float, top_p: float, hyperparams: JSONObject
) -> BaseEngine:
    settings = get_settings()
    # Lazy import so the API can still boot in minimal installs.
    from kani.engines.anthropic import AnthropicEngine

    return AnthropicEngine(
        api_key=settings.anthropic_api_key,
        model=model,
        temperature=temperature,
        top_p=top_p,
        **(hyperparams or {}),
    )


def _create_google_engine(
    *, model: str, temperature: float, top_p: float, hyperparams: JSONObject
) -> BaseEngine:
    settings = get_settings()
    # Lazy import so the API can still boot in minimal installs.
    from kani.engines.google import GoogleAIEngine

    return GoogleAIEngine(
        api_key=settings.gemini_api_key,
        model=model,
        temperature=temperature,
        top_p=top_p,
        **(hyperparams or {}),
    )


_ENGINE_FACTORIES = {
    "openai": _create_openai_engine,
    "anthropic": _create_anthropic_engine,
    "google": _create_google_engine,
}


# ---------------------------------------------------------------------------
# Resolve effective provider/model/hyperparams
# ---------------------------------------------------------------------------


def _resolve_model_config(
    *,
    mode: ChatMode,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> tuple[ModelProvider, str, float, float, JSONObject]:
    """Return (provider, model, temperature, top_p, merged_hyperparams).

    When *provider_override* / *model_override* are given they take precedence
    over the server-configured defaults.  If the caller passes a catalog ``id``
    (e.g. ``"openai/gpt-5"``) as *model_override* we resolve the native model
    name and provider from the catalog.
    """
    settings = get_settings()

    # 1. Start from server defaults for the given mode.
    if mode == "plan":
        provider: ModelProvider = settings.planning_provider
        model = settings.planning_model
        temperature = settings.planning_temperature
        top_p = settings.planning_top_p
        base_hyperparams = settings.planning_hyperparams
    else:
        provider = "openai"
        model = settings.openai_model
        temperature = settings.openai_temperature
        top_p = settings.openai_top_p
        base_hyperparams = settings.openai_hyperparams

    # 2. Apply per-request overrides.
    if model_override:
        # Try catalog lookup first (e.g. "openai/gpt-5" -> entry).
        entry = get_model_entry(model_override)
        if entry:
            provider = entry.provider
            model = entry.model
        else:
            # Treat as a raw provider-native model name.
            model = model_override

    if provider_override:
        provider = provider_override

    # 3. Merge hyperparams: base config + reasoning effort.
    merged: dict[str, object] = dict(base_hyperparams or {})
    reasoning_hp = build_reasoning_hyperparams(provider, reasoning_effort)
    merged.update(reasoning_hp)

    return provider, model, temperature, top_p, cast(JSONObject, merged)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_engine(
    *,
    mode: ChatMode,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> BaseEngine:
    """Create an LLM engine for *mode*, optionally overridden per-request."""
    provider, model, temperature, top_p, hyperparams = _resolve_model_config(
        mode=mode,
        provider_override=provider_override,
        model_override=model_override,
        reasoning_effort=reasoning_effort,
    )
    factory = _ENGINE_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(f"Unknown provider: {provider!r}")
    return factory(
        model=model,
        temperature=temperature,
        top_p=top_p,
        hyperparams=hyperparams,
    )


def create_agent(
    site_id: str,
    user_id: UUID | None = None,
    chat_history: list[ChatMessage] | None = None,
    strategy_graph: JSONObject | None = None,
    selected_nodes: JSONObject | None = None,
    delegation_draft_artifact: JSONObject | None = None,
    plan_session_id: UUID | None = None,
    get_plan_session_artifacts: Callable[[], Awaitable[JSONArray]] | None = None,
    mode: ChatMode = "execute",
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> PathfinderAgent | PathfinderPlannerAgent:
    """Create a new Pathfinder agent instance (executor or planner)."""
    engine = create_engine(
        mode=mode,
        provider_override=provider_override,
        model_override=model_override,
        reasoning_effort=reasoning_effort,
    )
    if mode == "plan":
        return PathfinderPlannerAgent(
            engine=engine,
            site_id=site_id,
            user_id=user_id,
            chat_history=chat_history,
            strategy_graph=strategy_graph,
            selected_nodes=selected_nodes,
            delegation_draft_artifact=delegation_draft_artifact,
            plan_session_id=plan_session_id,
            get_plan_session_artifacts=get_plan_session_artifacts,
        )
    return PathfinderAgent(
        engine=engine,
        site_id=site_id,
        user_id=user_id,
        chat_history=chat_history,
        strategy_graph=strategy_graph,
        selected_nodes=selected_nodes,
    )
