"""Engine creation helpers -- separated to avoid circular imports.

This module does NOT depend on executor.py or factory.py, so it can be
imported by both without circularity.
"""

from dataclasses import dataclass
from typing import cast

from kani.engines.base import BaseEngine
from kani.engines.google import GoogleAIEngine
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.ai.engines.cached_anthropic import CachedAnthropicEngine
from veupath_chatbot.ai.engines.mock import MockEngine
from veupath_chatbot.ai.engines.responses_openai import ResponsesOpenAIEngine
from veupath_chatbot.ai.models.catalog import (
    ModelProvider,
    ReasoningEffort,
    build_reasoning_hyperparams,
    get_model_entry,
)
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONObject

_ANTHROPIC_THINKING_BUDGET_THRESHOLD = 2048


@dataclass(frozen=True, slots=True)
class _ModelParams:
    """Resolved model parameters for engine creation."""

    provider: ModelProvider
    model: str
    temperature: float
    top_p: float
    hyperparams: JSONObject
    max_ctx: int | None = None
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Engine configuration for creating an LLM engine."""

    provider_override: ModelProvider | None = None
    model_override: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None
    seed: int | None = None
    context_size: int | None = None
    reasoning_budget: int | None = None


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
    kwargs: dict[str, object] = {}
    if max_context_size is not None:
        kwargs["max_context_size"] = max_context_size

    thinking_cfg = (hyperparams or {}).get("thinking")
    thinking_enabled = isinstance(thinking_cfg, dict) and thinking_cfg.get("type") in (
        "enabled",
        "adaptive",
    )
    if thinking_enabled and isinstance(thinking_cfg, dict):
        temperature = 1.0
        raw_budget = thinking_cfg.get("budget_tokens", 0)
        budget = int(raw_budget) if isinstance(raw_budget, (int, float)) else 0
        if budget >= _ANTHROPIC_THINKING_BUDGET_THRESHOLD:
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
    """Resolve effective model ID from override and persisted state."""
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

    return provider, model, temperature, top_p, cast("JSONObject", merged)


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


def _dispatch_engine(params: _ModelParams, *, site_id: str) -> BaseEngine:
    """Dispatch to the correct engine factory by provider."""
    if params.provider == "openai":
        return _create_openai_engine(
            model=params.model,
            temperature=params.temperature,
            top_p=params.top_p,
            hyperparams=params.hyperparams,
            seed=params.seed,
            max_context_size=params.max_ctx,
        )
    if params.provider == "anthropic":
        return _create_anthropic_engine(
            model=params.model,
            temperature=params.temperature,
            top_p=params.top_p,
            hyperparams=params.hyperparams,
            max_context_size=params.max_ctx,
        )
    if params.provider == "google":
        return _create_google_engine(
            model=params.model,
            temperature=params.temperature,
            top_p=params.top_p,
            hyperparams=params.hyperparams,
            max_context_size=params.max_ctx,
        )
    if params.provider == "ollama":
        return _create_ollama_engine(
            model=params.model,
            temperature=params.temperature,
            top_p=params.top_p,
            hyperparams=params.hyperparams,
            max_context_size=params.max_ctx,
        )
    if params.provider == "mock":
        return MockEngine(site_id=site_id)
    msg = f"Unknown provider: {params.provider!r}"
    raise ValueError(msg)


def create_engine(
    config: EngineConfig | None = None,
    *,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    site_id: str = "plasmodb",
) -> BaseEngine:
    """Create an LLM engine from config or individual overrides.

    Accepts either an EngineConfig or individual keyword overrides.
    If config is provided, its values take precedence over individual kwargs.
    """
    cfg = config or EngineConfig()
    eff_provider = provider_override or cfg.provider_override
    eff_model = model_override or cfg.model_override
    provider, model, resolved_temperature, top_p, hyperparams = _resolve_model_config(
        provider_override=eff_provider,
        model_override=eff_model,
        reasoning_effort=cfg.reasoning_effort,
        reasoning_budget=cfg.reasoning_budget,
    )
    effective_temperature = (
        cfg.temperature if cfg.temperature is not None else resolved_temperature
    )
    max_ctx = _resolve_context_size(eff_model, cfg.context_size)

    params = _ModelParams(
        provider=provider,
        model=model,
        temperature=effective_temperature,
        top_p=top_p,
        hyperparams=hyperparams,
        max_ctx=max_ctx,
        seed=cfg.seed,
    )
    return _dispatch_engine(params, site_id=site_id)
