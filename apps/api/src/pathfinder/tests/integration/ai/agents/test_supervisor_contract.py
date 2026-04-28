"""Cassette-backed contract test: real provider response parses cleanly into
``SupervisorDecision``.

Hand-rolled stubs (e.g. ``_stub_supervisor_agent`` in
``tests/unit/ai/graph/test_supervisor.py``) survive only as long as the
provider's wire format and pydantic-ai's output-extraction conventions
hold. This test pins the contract by recording one real round-trip per
provider and replaying via VCR cassettes on every push.

Recording (one-time, per provider):
    PATHFINDER_RECORD_AGENT_CASSETTES=1 \\
        ANTHROPIC_API_KEY=... \\
        uv run pytest src/pathfinder/tests/integration/ai/agents/test_supervisor_contract.py -v

Replay (every push, no API key required):
    uv run pytest src/pathfinder/tests/integration/ai/agents/test_supervisor_contract.py -v

When no cassette exists and not in record mode, the test is skipped with a
clear message — it does not block CI.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pydantic_ai.models
import pytest

from pathfinder.ai.agents.supervisor import (
    SupervisorDecision,
    SupervisorDeps,
    build_supervisor_agent,
)
from pathfinder.platform.types import ModelProvider

CASSETTE_DIR = Path(__file__).parent / "cassettes"
RECORD_FLAG = "PATHFINDER_RECORD_AGENT_CASSETTES"

# One cassette per provider keeps the contract specific — pydantic-ai
# extracts output from each provider's idiomatic tool-call shape (Anthropic
# `tool_use` blocks vs OpenAI function-calls vs Google parts), and a single
# bundled cassette would mask provider-specific drift.
PROVIDER_FIXTURES: dict[ModelProvider, str] = {
    "anthropic": "supervisor_anthropic_question.yaml",
    "openai": "supervisor_openai_question.yaml",
    "google": "supervisor_google_question.yaml",
}

PROBE_PROMPT = (
    "User just asked: 'What is gene-set enrichment?'. "
    "There is no problem frame yet. Decide where to route."
)
PROBE_STATE_BLOCK = (
    "Pipeline state: empty. No problem frame, no plan, no execution results."
)


@pytest.fixture
def allow_model_requests() -> Generator[None]:
    """Temporarily lift the global block on real LLM HTTP calls.

    Conftest sets ``pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`` so
    ordinary tests fail loudly if they hit a live provider. This contract
    test is the one place where a real call is intended (during recording);
    during replay, VCR intercepts before the HTTP layer so the flag is a
    moot belt-and-braces.
    """
    previous = pydantic_ai.models.ALLOW_MODEL_REQUESTS
    pydantic_ai.models.ALLOW_MODEL_REQUESTS = True
    try:
        yield
    finally:
        pydantic_ai.models.ALLOW_MODEL_REQUESTS = previous


def _cassette_path(provider: ModelProvider) -> Path:
    return CASSETTE_DIR / PROVIDER_FIXTURES[provider]


def _vcr_mode() -> str:
    if os.environ.get(RECORD_FLAG) == "1":
        return "new_episodes"
    return "none"


@pytest.fixture
def vcr_config() -> dict[str, object]:
    """pytest-recording hook — strip auth headers from cassettes.

    Without this every recorded cassette would leak the API key. The
    contract test only cares about the response *shape*, so request/response
    bodies stay; auth headers go.
    """
    return {
        "filter_headers": [
            ("authorization", "<REDACTED>"),
            ("x-api-key", "<REDACTED>"),
            ("anthropic-api-key", "<REDACTED>"),
            ("openai-api-key", "<REDACTED>"),
            ("x-goog-api-key", "<REDACTED>"),
        ],
        "record_mode": _vcr_mode(),
        "match_on": ["method", "scheme", "host", "path"],
    }


@pytest.mark.vcr
@pytest.mark.parametrize("provider", list(PROVIDER_FIXTURES.keys()))
@pytest.mark.usefixtures("allow_model_requests")
async def test_supervisor_response_parses_into_typed_output(
    provider: ModelProvider,
) -> None:
    cassette = _cassette_path(provider)
    recording = os.environ.get(RECORD_FLAG) == "1"

    if not cassette.is_file() and not recording:
        pytest.skip(
            f"no cassette at {cassette.relative_to(CASSETTE_DIR.parents[3])}; "
            f"record with {RECORD_FLAG}=1 + provider API key set",
        )

    agent = build_supervisor_agent(provider=provider)
    deps = SupervisorDeps(state_block=PROBE_STATE_BLOCK)

    result = await agent.run(PROBE_PROMPT, deps=deps)
    decision = result.output

    assert isinstance(decision, SupervisorDecision), (
        f"expected SupervisorDecision, got {type(decision).__name__}"
    )
    assert decision.to in {
        "scoping",
        "discovery",
        "planning",
        "execution",
        "verification",
        "end",
        "reject",
        "question",
    }, f"unknown target: {decision.to!r}"
    assert decision.reason.strip(), "reason must be non-empty"
    if decision.to == "question":
        assert decision.answer is not None
        assert decision.answer.strip()
    if decision.to == "reject":
        assert decision.rejection_message is not None
        assert decision.rejection_message.strip()
