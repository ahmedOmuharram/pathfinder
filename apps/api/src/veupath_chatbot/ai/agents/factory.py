"""Factory helpers for constructing the agent and its engine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, cast
from uuid import UUID

from kani import ChatMessage
from kani.engines.base import BaseEngine
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.ai.models.catalog import (
    ModelProvider,
    ReasoningEffort,
    build_reasoning_hyperparams,
    get_model_entry,
)
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONArray, JSONObject

from .executor import PathfinderAgent
from .planner import PathfinderPlannerAgent

ChatMode = Literal["execute", "plan"]


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
    return cast(
        BaseEngine,
        OpenAIEngine(
            api_key=settings.openai_api_key,
            model=model,
            **kwargs,
            **(hyperparams or {}),
        ),
    )


def _create_anthropic_engine(
    *, model: str, temperature: float, top_p: float, hyperparams: JSONObject
) -> BaseEngine:
    settings = get_settings()
    # Lazy import so the API can still boot in minimal installs.
    from kani.engines.anthropic import AnthropicEngine

    return cast(
        BaseEngine,
        AnthropicEngine(
            api_key=settings.anthropic_api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            **(hyperparams or {}),
        ),
    )


def _create_google_engine(
    *, model: str, temperature: float, top_p: float, hyperparams: JSONObject
) -> BaseEngine:
    settings = get_settings()
    # Lazy import so the API can still boot in minimal installs.
    from kani.engines.google import GoogleAIEngine

    return cast(
        BaseEngine,
        GoogleAIEngine(
            api_key=settings.gemini_api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
            **(hyperparams or {}),
        ),
    )


_ENGINE_FACTORIES = {
    "openai": _create_openai_engine,
    "anthropic": _create_anthropic_engine,
    "google": _create_google_engine,
}


def resolve_effective_model_id(
    *,
    model_override: str | None = None,
    persisted_model_id: str | None = None,
) -> str:
    """Resolve effective model ID from override and persisted state.

    Priority: per-request override > persisted per-conversation > server default.
    Used by the orchestrator to determine which model to persist back.

    :param model_override: Model ID override (default: None).
    :param persisted_model_id: Persisted model ID (default: None).
    :returns: Effective model ID.
    """
    return model_override or persisted_model_id or get_settings().default_model_id


def _resolve_model_config(
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> tuple[ModelProvider, str, float, float, JSONObject]:
    """Resolve provider, model, and hyperparams from overrides and defaults.

    Model selection is **mode-agnostic**: the same default applies to both
    planning and execution.  If the caller passes a catalog ``id`` (e.g.
    ``"openai/gpt-5"``) as *model_override* we resolve the native model name
    and provider from the catalog.

    :param provider_override: Provider override (default: None).
    :param model_override: Model ID override (default: None).
    :param reasoning_effort: Reasoning effort (default: None).
    :returns: Tuple of (provider, model, temperature, top_p, hyperparams).
    """
    settings = get_settings()

    # 1. Start from the unified server default.
    default_entry = get_model_entry(settings.default_model_id)
    if default_entry:
        provider: ModelProvider = default_entry.provider
        model = default_entry.model
    else:
        # Fallback when the configured default_model_id isn't in the catalog.
        provider = "openai"
        model = settings.openai_model

    # Sensible defaults — skipped by the engine constructor for
    # sampling-restricted models (gpt-5, o1, o3, o4).
    temperature = 0.0
    top_p = 1.0

    # 2. Apply per-request overrides.
    if model_override:
        entry = get_model_entry(model_override)
        if entry:
            provider = entry.provider
            model = entry.model
        else:
            # Treat as a raw provider-native model name.
            model = model_override

    if provider_override:
        provider = provider_override

    # 3. Determine effective reasoning effort.
    #    When no explicit effort is requested, apply the server-wide default
    #    for reasoning-capable models.
    effective_effort = reasoning_effort
    if effective_effort is None:
        resolved_entry = get_model_entry(model_override or settings.default_model_id)
        if resolved_entry and resolved_entry.supports_reasoning:
            effective_effort = settings.default_reasoning_effort

    # 4. Merge hyperparams (reasoning effort only — no per-mode base config).
    merged: dict[str, object] = {}
    reasoning_hp = build_reasoning_hyperparams(provider, effective_effort)
    merged.update(reasoning_hp)

    return provider, model, temperature, top_p, cast(JSONObject, merged)


def create_engine(
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> BaseEngine:
    """Create an LLM engine, optionally overridden per-request.

    Model selection is mode-agnostic; the same default applies everywhere.

    :param provider_override: Provider override (default: None).
    :param model_override: Model ID override (default: None).
    :param reasoning_effort: Reasoning effort (default: None).
    :returns: Configured LLM engine instance.
    """
    provider, model, temperature, top_p, hyperparams = _resolve_model_config(
        provider_override=provider_override,
        model_override=model_override,
        reasoning_effort=reasoning_effort,
    )
    factory = _ENGINE_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(f"Unknown provider: {provider!r}")
    return cast(
        BaseEngine,
        factory(
            model=model,
            temperature=temperature,
            top_p=top_p,
            hyperparams=hyperparams,
        ),
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
    mentioned_context: str | None = None,
) -> PathfinderAgent | PathfinderPlannerAgent:
    """Create a new Pathfinder agent instance (executor or planner).

    *mode* determines the agent **type** (executor vs planner), but does
    **not** influence model selection — any model works with any mode.

    :param site_id: VEuPathDB site identifier.
    :param user_id: User ID (default: None).
    :param chat_history: Chat history (default: None).
    :param strategy_graph: Strategy graph payload (default: None).
    :param selected_nodes: Selected nodes (default: None).
    :param delegation_draft_artifact: Delegation draft (default: None).
    :param plan_session_id: Plan session ID (default: None).
    :param get_plan_session_artifacts: Async callable to fetch plan artifacts (default: None).
    :param mode: Chat mode (default: "execute").
    :param provider_override: Model provider override (default: None).
    :param model_override: Model ID override (default: None).
    :param reasoning_effort: Reasoning effort (default: None).
    :param mentioned_context: Rich context from @-mentioned entities (default: None).
    :returns: Configured agent instance.
    """
    engine = create_engine(
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
            mentioned_context=mentioned_context,
        )
    return PathfinderAgent(
        engine=engine,
        site_id=site_id,
        user_id=user_id,
        chat_history=chat_history,
        strategy_graph=strategy_graph,
        selected_nodes=selected_nodes,
        mentioned_context=mentioned_context,
    )
