from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.lead.sub_agent_tools import (
    phase_default_model_id,
    phase_override_kwargs,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.config import get_settings
from pathfinder.platform.types import ReasoningEffort
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


def test_default_phase_model_comes_from_the_configured_tier() -> None:
    # With nothing pinned per phase, the model is the configured
    # (default_provider, default_tier) preset -- and the stable
    # ``provider:model`` id goes to pydantic-ai verbatim, since in v2 a bare
    # ``openai:`` prefix already means the Responses API.
    kwargs = phase_override_kwargs(_ctx(), "frame")
    assert kwargs["model"] == "openai:gpt-5.6-luna"


def test_anthropic_pick_enables_caching() -> None:
    kwargs = phase_override_kwargs(
        _ctx(phase_models={"frame": "anthropic:claude-opus-5"}),
        "frame",
    )
    assert kwargs["model"] == "anthropic:claude-opus-5"
    settings = kwargs["model_settings"]
    assert settings["anthropic_cache_instructions"] is True
    assert settings["anthropic_cache_tool_definitions"] is True
    assert settings["anthropic_cache_messages"] is True


def test_openai_pick_carries_no_anthropic_flags() -> None:
    kwargs = phase_override_kwargs(
        _ctx(phase_models={"execution": "openai:gpt-5.6-terra"}),
        "execution",
    )
    assert kwargs["model"] == "openai:gpt-5.6-terra"
    assert "anthropic_cache_instructions" not in kwargs["model_settings"]


def test_reasoning_effort_composes_with_caching() -> None:
    kwargs = phase_override_kwargs(
        _ctx(
            phase_models={"execution": "anthropic:claude-opus-5"},
            phase_reasoning={"execution": "high"},
        ),
        "execution",
    )
    settings = kwargs["model_settings"]
    assert settings["thinking"] == "high"
    assert settings["anthropic_cache_instructions"] is True


def testphase_default_model_id_stays_stable_for_cost() -> None:
    # The readback id used for cost attribution must remain the stable
    # ``provider:model`` catalog id.
    assert phase_default_model_id("frame") == "openai:gpt-5.6-luna"


def test_configured_tier_actually_drives_phase_model_and_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default tier happens to match the agents' baked model, so pin the
    wiring with a tier that does NOT: switching DEFAULT_TIER must move both the
    model and the reasoning effort for a phase the user has not pinned."""
    settings = get_settings()
    monkeypatch.setattr(settings, "default_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "default_tier", "quality", raising=False)

    frame = phase_override_kwargs(_ctx(), "frame")
    execution = phase_override_kwargs(_ctx(), "execution")

    # quality: reasoning phases on sol at high, the mechanical phase on terra.
    assert frame["model"] == "openai:gpt-5.6-sol"
    assert frame["model_settings"]["thinking"] == "high"
    assert execution["model"] == "openai:gpt-5.6-terra"
    assert execution["model_settings"]["thinking"] == "medium"


def test_explicit_phase_pick_outranks_the_configured_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "default_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "default_tier", "quality", raising=False)

    kwargs = phase_override_kwargs(
        _ctx(phase_models={"frame": "openai:gpt-5.6-terra"}), "frame"
    )
    assert kwargs["model"] == "openai:gpt-5.6-terra"
