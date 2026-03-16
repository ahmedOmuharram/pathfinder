"""Factory helpers for constructing the agent and its engine."""

from typing import cast
from uuid import UUID

from kani import ChatMessage
from kani.engines.base import BaseEngine
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.ai.engines.responses_openai import ResponsesOpenAIEngine
from veupath_chatbot.ai.models.catalog import (
    ModelProvider,
    ReasoningEffort,
    build_reasoning_hyperparams,
    get_model_entry,
)
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONObject

from .executor import PathfinderAgent


def _create_openai_engine(
    *,
    model: str,
    temperature: float,
    top_p: float,
    hyperparams: JSONObject,
    seed: int | None = None,
    max_context_size: int | None = None,
) -> BaseEngine:
    settings = get_settings()
    # Some OpenAI models only support default sampling params (temperature=1, top_p=1).
    # To avoid hard failures, we omit temperature/top_p entirely for those models.
    sampling_restricted = model.startswith(("gpt-5", "o1", "o3", "o4"))
    kwargs: dict[str, object] = {}
    if not sampling_restricted:
        kwargs["temperature"] = temperature
        kwargs["top_p"] = top_p
    if seed is not None:
        kwargs["seed"] = seed
    if max_context_size is not None:
        kwargs["max_context_size"] = max_context_size
    return ResponsesOpenAIEngine(
        api_key=settings.openai_api_key,
        model=model,
        **kwargs,
        **(hyperparams or {}),
    )


def _create_anthropic_engine(
    *,
    model: str,
    temperature: float,
    top_p: float,
    hyperparams: JSONObject,
    max_context_size: int | None = None,
) -> BaseEngine:
    settings = get_settings()
    from veupath_chatbot.ai.engines.cached_anthropic import CachedAnthropicEngine

    kwargs: dict[str, object] = {}
    if max_context_size is not None:
        kwargs["max_context_size"] = max_context_size

    # Anthropic extended thinking constraints:
    # - temperature must be 1 when thinking is enabled
    # - top_p/top_k must not be set when thinking is enabled
    # - budget_tokens must be < max_tokens
    thinking_cfg = (hyperparams or {}).get("thinking")
    thinking_enabled = isinstance(thinking_cfg, dict) and thinking_cfg.get("type") in (
        "enabled",
        "adaptive",
    )
    if thinking_enabled and isinstance(thinking_cfg, dict):
        temperature = 1.0
        # Don't pass top_p — Anthropic rejects it with thinking enabled.
        raw_budget = thinking_cfg.get("budget_tokens", 0)
        budget = int(raw_budget) if isinstance(raw_budget, (int, float)) else 0
        # max_tokens must exceed budget_tokens; default kani value (2048) is
        # too low for medium/high budgets.  Set to budget + 16 384 output room.
        if budget >= 2048:
            kwargs["max_tokens"] = budget + 16_384
    else:
        kwargs["top_p"] = top_p

    return CachedAnthropicEngine(
        api_key=settings.anthropic_api_key,
        model=model,
        temperature=temperature,
        **kwargs,
        **(hyperparams or {}),
    )


def _create_google_engine(
    *,
    model: str,
    temperature: float,
    top_p: float,
    hyperparams: JSONObject,
    max_context_size: int | None = None,
) -> BaseEngine:
    settings = get_settings()
    from kani.engines.google import GoogleAIEngine

    kwargs: dict[str, object] = {}
    if max_context_size is not None:
        kwargs["max_context_size"] = max_context_size
    return GoogleAIEngine(
        api_key=settings.gemini_api_key,
        model=model,
        temperature=temperature,
        top_p=top_p,
        **kwargs,
        **(hyperparams or {}),
    )


def _create_ollama_engine(
    *,
    model: str,
    temperature: float,
    top_p: float,
    hyperparams: JSONObject,
    max_context_size: int | None = None,
) -> BaseEngine:
    settings = get_settings()
    kwargs: dict[str, object] = {}
    if max_context_size is not None:
        kwargs["max_context_size"] = max_context_size
    return OpenAIEngine(
        api_key="ollama",
        model=model,
        api_base=settings.ollama_base_url,
        temperature=temperature,
        top_p=top_p,
        **kwargs,
        **(hyperparams or {}),
    )


def resolve_effective_model_id(
    *,
    model_override: str | None = None,
    persisted_model_id: str | None = None,
) -> str:
    """Resolve effective model ID from override and persisted state.

    Priority: per-request override > persisted per-conversation > server default.
    """
    return model_override or persisted_model_id or get_settings().default_model_id


def _resolve_model_config(
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    reasoning_budget: int | None = None,
) -> tuple[ModelProvider, str, float, float, JSONObject]:
    """Resolve provider, model, and hyperparams from overrides and defaults."""
    settings = get_settings()

    default_entry = get_model_entry(settings.default_model_id)
    if default_entry:
        provider: ModelProvider = default_entry.provider
        model = default_entry.model
    else:
        provider = "openai"
        model = settings.openai_model

    temperature = 0.0
    top_p = 1.0

    if model_override:
        entry = get_model_entry(model_override)
        if entry:
            provider = entry.provider
            model = entry.model
        else:
            model = model_override

    if provider_override:
        provider = provider_override

    resolved_entry = get_model_entry(model_override or settings.default_model_id)
    supports_reasoning = resolved_entry.supports_reasoning if resolved_entry else False

    effective_effort: ReasoningEffort | None = None
    if supports_reasoning:
        effective_effort = reasoning_effort
        if effective_effort is None:
            effective_effort = settings.default_reasoning_effort

    merged: dict[str, object] = {}
    reasoning_hp = build_reasoning_hyperparams(
        provider, effective_effort, budget_override=reasoning_budget
    )
    merged.update(reasoning_hp)

    return provider, model, temperature, top_p, cast(JSONObject, merged)


def _resolve_context_size(
    model_override: str | None,
    context_size_override: int | None,
) -> int | None:
    """Resolve context size: per-request override > catalog > engine default."""
    if context_size_override is not None and context_size_override > 0:
        return context_size_override
    entry = get_model_entry(model_override or get_settings().default_model_id)
    if entry and entry.context_size > 0:
        return entry.context_size
    return None


def create_engine(
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    context_size: int | None = None,
    reasoning_budget: int | None = None,
    site_id: str = "plasmodb",
) -> BaseEngine:
    """Create an LLM engine, optionally overridden per-request."""
    provider, model, resolved_temperature, top_p, hyperparams = _resolve_model_config(
        provider_override=provider_override,
        model_override=model_override,
        reasoning_effort=reasoning_effort,
        reasoning_budget=reasoning_budget,
    )
    effective_temperature = (
        temperature if temperature is not None else resolved_temperature
    )
    max_ctx = _resolve_context_size(model_override, context_size)

    if provider == "openai":
        return _create_openai_engine(
            model=model,
            temperature=effective_temperature,
            top_p=top_p,
            hyperparams=hyperparams,
            seed=seed,
            max_context_size=max_ctx,
        )
    if provider == "anthropic":
        return _create_anthropic_engine(
            model=model,
            temperature=effective_temperature,
            top_p=top_p,
            hyperparams=hyperparams,
            max_context_size=max_ctx,
        )
    if provider == "google":
        return _create_google_engine(
            model=model,
            temperature=effective_temperature,
            top_p=top_p,
            hyperparams=hyperparams,
            max_context_size=max_ctx,
        )
    if provider == "ollama":
        return _create_ollama_engine(
            model=model,
            temperature=effective_temperature,
            top_p=top_p,
            hyperparams=hyperparams,
            max_context_size=max_ctx,
        )
    if provider == "mock":
        from veupath_chatbot.ai.engines.mock import MockEngine

        return MockEngine(site_id=site_id)
    raise ValueError(f"Unknown provider: {provider!r}")


def create_agent(
    site_id: str,
    user_id: UUID | None = None,
    chat_history: list[ChatMessage] | None = None,
    strategy_graph: JSONObject | None = None,
    selected_nodes: JSONObject | None = None,
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    mentioned_context: str | None = None,
    disable_rag: bool = False,
    temperature: float | None = None,
    seed: int | None = None,
    context_size: int | None = None,
    response_tokens: int | None = None,
    reasoning_budget: int | None = None,
) -> PathfinderAgent:
    """Create a unified Pathfinder agent instance."""
    engine = create_engine(
        provider_override=provider_override,
        model_override=model_override,
        reasoning_effort=reasoning_effort,
        temperature=temperature,
        seed=seed,
        context_size=context_size,
        reasoning_budget=reasoning_budget,
        site_id=site_id,
    )
    return PathfinderAgent(
        engine=engine,
        site_id=site_id,
        user_id=user_id,
        chat_history=chat_history,
        strategy_graph=strategy_graph,
        selected_nodes=selected_nodes,
        mentioned_context=mentioned_context,
        disable_rag=disable_rag,
        desired_response_tokens=response_tokens,
    )
