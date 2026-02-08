"""Factory helpers for constructing the agent and its engine."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, cast
from uuid import UUID

from kani import ChatMessage
from kani.engines.base import BaseEngine
from kani.engines.openai import OpenAIEngine

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONArray, JSONObject

from .agent_runtime import PathfinderAgent
from .planner_runtime import PathfinderPlannerAgent

ChatMode = Literal["execute", "plan"]
ModelProvider = Literal["openai", "anthropic", "google"]


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


def create_engine(*, mode: ChatMode) -> BaseEngine:
    settings = get_settings()
    if mode == "plan":
        provider: ModelProvider = settings.planning_provider
        model = settings.planning_model
        temperature = settings.planning_temperature
        top_p = settings.planning_top_p
        hyperparams_raw = settings.planning_hyperparams
    else:
        provider = "openai"
        model = settings.openai_model
        temperature = settings.openai_temperature
        top_p = settings.openai_top_p
        hyperparams_raw = settings.openai_hyperparams

    hyperparams = cast(JSONObject, hyperparams_raw or {})

    if provider == "openai":
        return _create_openai_engine(
            model=model, temperature=temperature, top_p=top_p, hyperparams=hyperparams
        )
    if provider == "anthropic":
        return _create_anthropic_engine(
            model=model, temperature=temperature, top_p=top_p, hyperparams=hyperparams
        )
    return _create_google_engine(
        model=model, temperature=temperature, top_p=top_p, hyperparams=hyperparams
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
) -> PathfinderAgent | PathfinderPlannerAgent:
    """Create a new Pathfinder agent instance (executor or planner)."""
    engine = create_engine(mode=mode)
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
