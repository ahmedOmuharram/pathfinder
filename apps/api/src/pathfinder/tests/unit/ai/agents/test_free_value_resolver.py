"""A parameter with no vocabulary still has an answer in the request.

The vocabulary resolver can only choose from candidates, so a param with no
candidates -- a number, a free-text term -- gets nothing from it. Measured
against the gold corpus that is the largest remaining bucket: of the 237 params
no named rule covers, 69 (29%) are bare numerics.

Live, that produced a turn that asked the scientist for five values they had
already written: "Minimum unique peptide sequences: 2. Minimum spectra per gene
per sample: 2. Text search term: kinase." All three are in the request.

The guarantee differs from the vocabulary case and the difference matters. There
is no candidate list to check an answer against, so the backstop is WDK's own
validation, which already answers a bad value with a did-you-mean retry. What is
NOT acceptable is inventing a value the request does not state -- that is how
`GenesByText` inheriting its `*reductase` example turned an odorant-binding
protein search into a reductase search. Silence must stay silence.
"""

from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from pathfinder.ai.agents import vocab_resolver
from pathfinder.ai.agents.vocab_resolver import FreeValue, resolve_free_value


def _answering(value: str | None) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        del messages
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name, {"value": value, "reason": "test"}
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
                ToolCallPart(info.output_tools[0].name, {"value": "2", "reason": ""})
            ]
        )

    return FunctionModel(respond)


def _install(monkeypatch: pytest.MonkeyPatch, model: FunctionModel) -> None:
    agent = Agent(model, output_type=FreeValue, name="free_value_test")
    monkeypatch.setattr(vocab_resolver, "free_value_agent", lambda: agent)


class TestItReadsTheRequest:
    @pytest.mark.asyncio
    async def test_a_number_stated_in_the_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("2"))

        chosen = await resolve_free_value(
            "at least 2 peptides and 2 spectra in trophozoite samples",
            param_name="min_peptides",
            param_type="number",
            help_text="Minimum unique peptide sequences",
        )

        assert chosen == "2"

    @pytest.mark.asyncio
    async def test_a_free_text_term_stated_in_the_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("kinase"))

        chosen = await resolve_free_value(
            "text search for 'kinase'",
            param_name="text_expression",
            param_type="string",
            help_text="Text term",
        )

        assert chosen == "kinase"


class TestSilenceStaysSilence:
    @pytest.mark.asyncio
    async def test_null_is_none_not_a_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The request says nothing about this param. Inventing a plausible value
        # here is exactly the `*reductase` failure.
        _install(monkeypatch, _answering(None))

        chosen = await resolve_free_value(
            "kinases expressed in trophozoites",
            param_name="text_expression",
            param_type="string",
            help_text="Text term",
        )

        assert chosen is None

    @pytest.mark.asyncio
    async def test_an_empty_answer_is_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install(monkeypatch, _answering("   "))

        chosen = await resolve_free_value(
            "anything",
            param_name="p",
            param_type="string",
            help_text="",
        )

        assert chosen is None


class TestThePromptCarriesWhatItNeeds:
    @pytest.mark.asyncio
    async def test_the_param_name_and_help_reach_the_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Without the help text "min_peptides" is an opaque token, and the model
        # cannot tell which of two numbers in the sentence belongs to it.
        prompts: list[str] = []
        _install(monkeypatch, _capturing(prompts))

        await resolve_free_value(
            "at least 2 peptides and 3 spectra",
            param_name="min_peptides",
            param_type="number",
            help_text="Minimum unique peptide sequences",
        )

        assert prompts
        assert "min_peptides" in prompts[-1]
        assert "Minimum unique peptide sequences" in prompts[-1]
