from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.conversation.request_body import ReasoningEffort
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.lead.sub_agent_tools import (
    _phase_default_model_id,
    _phase_override_kwargs,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.config import get_settings
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService


@pytest.fixture(autouse=True)
def _real_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """These tests exercise the real model-translation path; the suite-wide
    default provider is ``mock``, which short-circuits the override."""
    monkeypatch.setenv("PATHFINDER_CHAT_PROVIDER", "default")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-for-model-translation")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _never_factory() -> AsyncSession:
    msg = "db factory should not be called in unit tests"
    raise AssertionError(msg)


def _ctx(
    *,
    phase_models: dict[PhaseRole, str] | None = None,
    phase_reasoning: dict[PhaseRole, ReasoningEffort] | None = None,
) -> Context:
    return Context(
        site_id="plasmodb",
        user_id=uuid4(),
        strategy_session=StrategySession(site_id="plasmodb"),
        db_session_factory=_never_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        phase_models=phase_models or {},
        phase_reasoning=phase_reasoning or {},
    )


def test_default_phase_model_translated_to_responses() -> None:
    kwargs = _phase_override_kwargs(_ctx(), "discovery")
    assert kwargs["model"] == "openai-responses:gpt-5-mini"


def test_anthropic_pick_enables_caching() -> None:
    kwargs = _phase_override_kwargs(
        _ctx(phase_models={"discovery": "anthropic:claude-opus-4-6"}),
        "discovery",
    )
    assert kwargs["model"] == "anthropic:claude-opus-4-6"
    settings = kwargs["model_settings"]
    assert settings["anthropic_cache_instructions"] is True
    assert settings["anthropic_cache_tool_definitions"] is True
    assert settings["anthropic_cache_messages"] is True


def test_openai_pick_translated_without_anthropic_flags() -> None:
    kwargs = _phase_override_kwargs(
        _ctx(phase_models={"planning": "openai:gpt-5.4"}),
        "planning",
    )
    assert kwargs["model"] == "openai-responses:gpt-5.4"
    assert "anthropic_cache_instructions" not in kwargs["model_settings"]


def test_reasoning_effort_composes_with_caching() -> None:
    kwargs = _phase_override_kwargs(
        _ctx(
            phase_models={"planning": "anthropic:claude-opus-4-6"},
            phase_reasoning={"planning": "high"},
        ),
        "planning",
    )
    settings = kwargs["model_settings"]
    assert settings["thinking"] == "high"
    assert settings["anthropic_cache_instructions"] is True


def test_phase_default_model_id_stays_stable_for_cost() -> None:
    # The readback id used for cost attribution must remain the stable
    # ``openai:`` id, NOT the translated ``openai-responses:`` inference name.
    assert _phase_default_model_id("discovery") == "openai:gpt-5-mini"
