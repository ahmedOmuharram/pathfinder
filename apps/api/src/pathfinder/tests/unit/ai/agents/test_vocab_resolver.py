"""The resolver's two guarantees, and its cost ceiling.

It answers with a value it was shown or with nothing, and nothing becomes a
question rather than a WDK default. Both matter more than its accuracy: a
resolver that is merely wrong produces a retry, while one that invents a value
or degrades to a default produces a strategy that silently answers a different
question.

Sizes measured live on 2026-08-10: the portal's InterPro vocabulary is 12,113
entries, about 219K tokens. Shortlisting keeps a real call near 4K;
``MAX_PROMPT_TOKENS`` is the backstop for the case nobody anticipated.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from pathfinder.ai.agents import vocab_resolver
from pathfinder.ai.agents.vocab_resolver import (
    MAX_PROMPT_TOKENS,
    VocabDecision,
    resolve_vocabulary_value,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption

_CANDIDATES = [
    VocabOption(value="yes", display="yes"),
    VocabOption(value="no", display="no"),
]


def _answering(value: str | None) -> FunctionModel:
    """A model that always answers ``value`` through the structured output tool."""

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"values": [] if value is None else [value], "reason": "test"},
                )
            ]
        )

    return FunctionModel(respond)


def _capturing(prompts: list[str]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        for message in messages:
            for part in message.parts:
                content = getattr(part, "content", None)
                if isinstance(content, str):
                    prompts.append(content)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name, {"values": ["no"], "reason": ""}
                )
            ]
        )

    return FunctionModel(respond)


def _install(monkeypatch: pytest.MonkeyPatch, model: FunctionModel) -> None:
    """Replace the lazily-built agent. The real one is built on first use so
    importing the module never opens a provider client."""
    agent = Agent(model, output_type=VocabDecision, name="vocab_resolver_test")
    monkeypatch.setattr(vocab_resolver, "resolver_agent", lambda: agent)


class TestItAnswers:
    @pytest.mark.asyncio
    async def test_a_candidate_value_is_returned(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("no"))

        assert (
            await resolve_vocabulary_value(
                "non-syntenic",
                param_name="p",
                param_help="",
                accepts_many=False,
                candidates=_CANDIDATES,
            )
            == "no"
        )

    @pytest.mark.asyncio
    async def test_null_is_returned_as_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering(None))

        assert (
            await resolve_vocabulary_value(
                "unrelated",
                param_name="p",
                param_help="",
                accepts_many=False,
                candidates=_CANDIDATES,
            )
            is None
        )


class TestItCannotInvent:
    @pytest.mark.asyncio
    async def test_a_value_outside_the_candidates_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # "Non-syntenic" is exactly what the real model produced against WDK,
        # and exactly what WDK rejected.
        _install(monkeypatch, _answering("Non-syntenic"))

        assert (
            await resolve_vocabulary_value(
                "non-syntenic",
                param_name="p",
                param_help="",
                accepts_many=False,
                candidates=_CANDIDATES,
            )
            is None
        )


class TestItNeverRaises:
    @pytest.mark.asyncio
    async def test_no_candidates_is_none_not_an_error(self) -> None:
        assert (
            await resolve_vocabulary_value(
                "anything",
                param_name="p",
                param_help="",
                accepts_many=False,
                candidates=[],
            )
            is None
        )


class TestTheCostCeiling:
    @pytest.mark.asyncio
    async def test_a_pathological_vocabulary_is_truncated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Each option is ~1KB, so 2,000 of them is ~2M chars against a budget of
        # MAX_PROMPT_TOKENS * 3.
        huge = [VocabOption(value=f"V{i:05}", display="x" * 1000) for i in range(2000)]
        prompts: list[str] = []
        _install(monkeypatch, _capturing(prompts))

        await resolve_vocabulary_value(
            "pick one",
            param_name="p",
            param_help="",
            accepts_many=False,
            candidates=huge,
        )

        assert prompts
        assert len(prompts[-1]) <= MAX_PROMPT_TOKENS * 4, "budget guard did not bind"

    @pytest.mark.asyncio
    async def test_a_normal_vocabulary_is_sent_whole(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prompts: list[str] = []
        _install(monkeypatch, _capturing(prompts))

        await resolve_vocabulary_value(
            "non-syntenic",
            param_name="p",
            param_help="",
            accepts_many=False,
            candidates=_CANDIDATES,
        )

        assert prompts
        assert "yes" in prompts[-1]
        assert "no" in prompts[-1]


class TestItAcceptsTheRenderedForm:
    """The candidates are rendered as ``- value  (display)``, so a model that
    copies "exactly" often returns that whole line.

    Observed: the resolver correctly chose ``DeRisi 3D7 Smoothed`` and
    answered ``"DeRisi 3D7 Smoothed  (iRBC 3D7 (48 Hour scaled))"``. A byte
    comparison against the value alone rejected it, the right answer was thrown
    away, and the criterion fell back to the HB3 default -- a different
    experiment. Matching an answer back to a candidate is the caller's job; only
    an answer that matches nothing is a refusal.
    """

    _PROFILESETS: ClassVar[list[VocabOption]] = [
        VocabOption(value="DeRisi 3D7 Smoothed", display="iRBC 3D7 (48 Hour scaled)"),
        VocabOption(value="DeRisi HB3 Smoothed", display="iRBC HB3"),
    ]

    @pytest.mark.asyncio
    async def test_the_rendered_line_resolves_to_its_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(
            monkeypatch,
            _answering("DeRisi 3D7 Smoothed  (iRBC 3D7 (48 Hour scaled))"),
        )

        chosen = await resolve_vocabulary_value(
            "DeRisi 3D7",
            param_name="p",
            param_help="",
            accepts_many=False,
            candidates=self._PROFILESETS,
        )

        assert chosen == "DeRisi 3D7 Smoothed"

    @pytest.mark.asyncio
    async def test_the_display_alone_resolves_to_its_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("iRBC 3D7 (48 Hour scaled)"))

        chosen = await resolve_vocabulary_value(
            "DeRisi 3D7",
            param_name="p",
            param_help="",
            accepts_many=False,
            candidates=self._PROFILESETS,
        )

        assert chosen == "DeRisi 3D7 Smoothed"

    @pytest.mark.asyncio
    async def test_a_leading_bullet_is_tolerated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("- DeRisi 3D7 Smoothed"))

        chosen = await resolve_vocabulary_value(
            "DeRisi 3D7",
            param_name="p",
            param_help="",
            accepts_many=False,
            candidates=self._PROFILESETS,
        )

        assert chosen == "DeRisi 3D7 Smoothed"

    @pytest.mark.asyncio
    async def test_something_matching_nothing_is_still_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("DeRisi Dd2 Smoothed"))

        assert (
            await resolve_vocabulary_value(
                "DeRisi Dd2",
                param_name="p",
                param_help="",
                accepts_many=False,
                candidates=self._PROFILESETS,
            )
            is None
        )
