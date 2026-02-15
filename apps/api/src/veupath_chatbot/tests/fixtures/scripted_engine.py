"""Scriptable Kani engine for integration tests.

Replaces the real LLM engine so the agent's tool dispatch, streaming,
event processing, and persistence all run real code while only the
LLM decisions are pre-scripted.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any

from kani.ai_function import AIFunction
from kani.engines.base import BaseCompletion, BaseEngine, Completion
from kani.models import ChatMessage, ChatRole, FunctionCall, ToolCall


@dataclass
class ScriptedToolCall:
    """A single tool call the 'LLM' should request."""

    name: str
    arguments: dict[str, Any]
    call_id: str | None = None  # auto-generated if None

    _counter: int = field(default=0, init=False, repr=False)

    def to_kani_tool_call(self, index: int = 0) -> ToolCall:
        call_id = self.call_id or f"tc_{index}"
        return ToolCall(
            id=call_id,
            type="function",
            function=FunctionCall(
                name=self.name,
                arguments=json.dumps(self.arguments),
            ),
        )


@dataclass
class ScriptedTurn:
    """One 'LLM response' in the scripted conversation.

    A turn can be:
    - text-only (content set, tool_calls empty) → assistant message
    - tool-calls-only (content None, tool_calls set) → agent dispatches tools then asks engine again
    - both (content + tool_calls) → some engines do this; Kani handles it


    """

    content: str | None = None
    tool_calls: list[ScriptedToolCall] | None = None
    # Optional: assertion on the last message in the conversation (for validating tool results)
    assert_last_message: Callable[[ChatMessage], None] | None = None


class ScriptedKaniEngine(BaseEngine):
    """A Kani-compatible engine that returns pre-scripted responses.

    Usage::

        engine = ScriptedKaniEngine([
            ScriptedTurn(tool_calls=[ScriptedToolCall("search_for_searches", {"query": "..."})]),
            ScriptedTurn(tool_calls=[ScriptedToolCall("create_step", {"search_name": "..."})]),
            ScriptedTurn(content="I've created the strategy for you."),
        ])
        agent = PathfinderAgent(engine=engine, site_id="plasmodb")


    """

    max_context_size = 1_000_000  # Effectively unlimited for tests

    def __init__(self, turns: list[ScriptedTurn]) -> None:
        self.turns = turns
        self._turn_index = 0
        self._exhausted = False

    @property
    def turns_remaining(self) -> int:
        return len(self.turns) - self._turn_index

    def prompt_len(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **kwargs: Any,
    ) -> int:
        # Return a small constant — tests don't care about context window limits.
        return 100

    async def predict(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **hyperparams: Any,
    ) -> BaseCompletion:
        if self._turn_index >= len(self.turns):
            if self._exhausted:
                raise RuntimeError(
                    f"ScriptedKaniEngine: script exhausted after {len(self.turns)} turns. "
                    "The agent requested more LLM calls than the test script provides. "
                    "Add more ScriptedTurn entries or check that tools are not causing extra rounds."
                )
            # First time we go past the script — return a final text to end the round
            self._exhausted = True
            return Completion(
                message=ChatMessage.assistant("Done."),
                prompt_tokens=0,
                completion_tokens=0,
            )

        turn = self.turns[self._turn_index]
        self._turn_index += 1

        # Optionally run assertion on the last message (useful for checking tool results)
        if turn.assert_last_message is not None and messages:
            turn.assert_last_message(messages[-1])

        # Build the ChatMessage
        tool_calls_kani: list[ToolCall] | None = None
        if turn.tool_calls:
            tool_calls_kani = [
                tc.to_kani_tool_call(index=i) for i, tc in enumerate(turn.tool_calls)
            ]

        msg = ChatMessage(
            role=ChatRole.ASSISTANT,
            content=turn.content,
            tool_calls=tool_calls_kani,
        )

        return Completion(message=msg, prompt_tokens=0, completion_tokens=0)

    async def stream(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **hyperparams: Any,
    ) -> AsyncIterable[str | BaseCompletion]:
        """Stream the scripted response token-by-token for realism."""
        completion = await self.predict(messages, functions, **hyperparams)
        msg = completion.message

        # Stream text content word-by-word
        if msg.content:
            words = msg.content.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else f" {word}"
                yield token

        # Yield the completion as the final element (required by Kani streaming contract)
        yield completion

    async def close(self) -> None:
        pass


ScriptedEngineFactory = Callable[
    [list[ScriptedTurn]], AbstractContextManager[ScriptedKaniEngine]
]
