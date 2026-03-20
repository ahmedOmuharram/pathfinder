"""Unit tests for MockEngine — the deterministic kani engine for E2E testing."""

import pytest
from kani.engines.base import BaseCompletion
from kani.models import ChatMessage, ChatRole

from veupath_chatbot.ai.engines.mock import MockEngine


class TestMockEnginePredict:
    """Test predict() keyword routing and multi-turn awareness."""

    @pytest.mark.asyncio
    async def test_default_message_returns_plain_text(self) -> None:
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("Hello")]
        completion = await engine.predict(messages)

        assert completion.message.role == ChatRole.ASSISTANT
        assert completion.message.text is not None
        assert "[mock]" in completion.message.text
        assert "Hello" in completion.message.text
        assert completion.message.tool_calls is None

    @pytest.mark.asyncio
    async def test_artifact_graph_returns_save_planning_artifact_call(self) -> None:
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("artifact graph")]
        completion = await engine.predict(messages)

        msg = completion.message
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        tc = msg.tool_calls[0]
        assert tc.function.name == "save_planning_artifact"
        args = tc.function.kwargs
        assert "proposed_strategy_plan" in args
        plan = args["proposed_strategy_plan"]
        assert plan["root"]["searchName"] == "GenesByTaxon"
        assert "Plasmodium falciparum 3D7" in plan["root"]["parameters"]["organism"]

    @pytest.mark.asyncio
    async def test_delegation_returns_delegate_strategy_subtasks_call(self) -> None:
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("delegation")]
        completion = await engine.predict(messages)

        msg = completion.message
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        tc = msg.tool_calls[0]
        assert tc.function.name == "delegate_strategy_subtasks"
        args = tc.function.kwargs
        assert "goal" in args
        assert "plan" in args

    @pytest.mark.asyncio
    async def test_delegation_draft_returns_save_planning_artifact(self) -> None:
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("delegation draft")]
        completion = await engine.predict(messages)

        msg = completion.message
        assert msg.tool_calls is not None
        tc = msg.tool_calls[0]
        assert tc.function.name == "save_planning_artifact"
        args = tc.function.kwargs
        assert "delegationGoal" in args.get("parameters", {})

    @pytest.mark.asyncio
    async def test_create_step_returns_create_step_call(self) -> None:
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("create step")]
        completion = await engine.predict(messages)

        msg = completion.message
        assert msg.tool_calls is not None
        tc = msg.tool_calls[0]
        assert tc.function.name == "create_step"
        args = tc.function.kwargs
        assert args["search_name"] == "GenesByTaxon"
        assert args["record_type"] == "gene"
        assert "Plasmodium falciparum 3D7" in args["parameters"]["organism"]

    @pytest.mark.asyncio
    async def test_post_tool_turn_returns_plain_text(self) -> None:
        """After a function result, predict returns text (exits full_round loop)."""
        engine = MockEngine(site_id="plasmodb")
        messages = [
            ChatMessage.user("create step"),
            ChatMessage.assistant(content=None, tool_calls=[]),
            ChatMessage.function("create_step", '{"ok": true}', tool_call_id="tc_0"),
        ]
        completion = await engine.predict(messages)

        assert completion.message.role == ChatRole.ASSISTANT
        assert completion.message.text is not None
        assert "[mock]" in completion.message.text
        assert completion.message.tool_calls is None

    @pytest.mark.asyncio
    async def test_site_specific_organism_toxodb(self) -> None:
        engine = MockEngine(site_id="toxodb")
        messages = [ChatMessage.user("create step")]
        completion = await engine.predict(messages)

        tc = completion.message.tool_calls[0]
        args = tc.function.kwargs
        assert "Toxoplasma gondii ME49" in args["parameters"]["organism"]

    @pytest.mark.asyncio
    async def test_site_specific_organism_tritrypdb(self) -> None:
        engine = MockEngine(site_id="tritrypdb")
        messages = [ChatMessage.user("artifact graph")]
        completion = await engine.predict(messages)

        tc = completion.message.tool_calls[0]
        plan = tc.function.kwargs["proposed_strategy_plan"]
        assert (
            "Leishmania major strain Friedlin" in plan["root"]["parameters"]["organism"]
        )

    @pytest.mark.asyncio
    async def test_unknown_site_falls_back_to_plasmodb(self) -> None:
        engine = MockEngine(site_id="unknowndb")
        messages = [ChatMessage.user("create step")]
        completion = await engine.predict(messages)

        tc = completion.message.tool_calls[0]
        args = tc.function.kwargs
        assert "Plasmodium falciparum 3D7" in args["parameters"]["organism"]

    @pytest.mark.asyncio
    async def test_delegation_keyword_priority_over_delegation_draft(self) -> None:
        """'delegation draft' should match before 'delegation'."""
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("show me the delegation draft plan")]
        completion = await engine.predict(messages)

        tc = completion.message.tool_calls[0]
        assert tc.function.name == "save_planning_artifact"


class TestMockEngineStream:
    """Test stream() yields tokens word-by-word."""

    @pytest.mark.asyncio
    async def test_stream_yields_tokens_and_completion(self) -> None:
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("Hello world")]

        tokens: list[str] = []
        completion: BaseCompletion | None = None
        async for item in engine.stream(messages):
            if isinstance(item, str):
                tokens.append(item)
            else:
                completion = item

        assert len(tokens) > 0
        assert completion is not None
        assert completion.message.role == ChatRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_stream_tool_call_yields_completion_only(self) -> None:
        """Tool calls have no text content, so stream yields only the Completion."""
        engine = MockEngine(site_id="plasmodb")
        messages = [ChatMessage.user("create step")]

        items = [item async for item in engine.stream(messages)]

        # Should have exactly one item: the Completion with tool calls
        assert len(items) == 1
        assert isinstance(items[0], BaseCompletion)
        assert items[0].message.tool_calls is not None


class TestMockEnginePromptLen:
    """Test prompt_len returns reasonable values."""

    def test_prompt_len_sums_message_text(self) -> None:
        engine = MockEngine()
        messages = [
            ChatMessage.user("Hello"),
            ChatMessage.assistant("Hi there"),
        ]
        length = engine.prompt_len(messages)
        assert length == len("Hello") + len("Hi there")

    def test_prompt_len_handles_none_content(self) -> None:
        engine = MockEngine()
        messages = [ChatMessage.assistant(content=None)]
        length = engine.prompt_len(messages)
        assert length == 0
