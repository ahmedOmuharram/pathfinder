"""Unit tests for :mod:`pathfinder.ai.graph.messages_reducer`."""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from pathfinder.ai.graph.messages_reducer import append_messages_safely


def _user(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _assistant(
    *parts: TextPart | ToolCallPart,
) -> ModelResponse:
    return ModelResponse(parts=list(parts))


def _tool_return(call_id: str, name: str = "foo") -> ModelRequest:
    return ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name=name, content="ok", tool_call_id=call_id,
            ),
        ],
    )


def _tool_call(call_id: str, name: str = "foo") -> ToolCallPart:
    return ToolCallPart(tool_name=name, args={}, tool_call_id=call_id)


class TestAppendMessagesSafely:
    def test_clean_history_passes_through_unchanged(self) -> None:
        existing = [_user("hi")]
        new = [_assistant(TextPart(content="hello"))]
        result = append_messages_safely(existing, new)
        assert result == existing + new

    def test_paired_tool_call_and_return_preserved(self) -> None:
        existing = [_user("hi"), _assistant(_tool_call("c1"))]
        new = [_tool_return("c1"), _assistant(TextPart(content="done"))]
        result = append_messages_safely(existing, new)
        assert len(result) == 4
        assert any(
            isinstance(p, ToolReturnPart) and p.tool_call_id == "c1"
            for m in result
            for p in m.parts
        )

    def test_orphan_tool_return_is_dropped(self) -> None:
        """A ToolReturnPart with no matching ToolCallPart is stripped."""
        existing = [_user("hi")]
        new = [_tool_return("phantom")]  # no preceding ToolCallPart
        result = append_messages_safely(existing, new)
        assert result == existing  # entire orphan-return ModelRequest dropped

    def test_orphan_tool_call_gets_placeholder_return(self) -> None:
        """A ToolCallPart with no matching ToolReturnPart gets a placeholder."""
        existing = [_user("hi"), _assistant(_tool_call("c1"))]
        new: list = []  # stream died before the return landed
        result = append_messages_safely(existing, new)
        # A synthetic ModelRequest with the placeholder return was appended.
        assert len(result) == 3
        last = result[-1]
        assert isinstance(last, ModelRequest)
        assert len(last.parts) == 1
        placeholder = last.parts[0]
        assert isinstance(placeholder, ToolReturnPart)
        assert placeholder.tool_call_id == "c1"
        assert isinstance(placeholder.content, str)
        assert "not executed" in placeholder.content.lower()

    def test_orphan_call_placeholder_inserted_into_next_request(self) -> None:
        """Placeholder is injected into the next ModelRequest when one exists."""
        existing = [
            _user("hi"),
            _assistant(_tool_call("c1")),
        ]
        # A later user turn lands with no tool return for c1.
        new = [_user("follow-up")]
        result = append_messages_safely(existing, new)
        # The follow-up request now carries both the user prompt and the
        # synthetic return so the earlier call_id is paired.
        follow_up = result[2]
        assert isinstance(follow_up, ModelRequest)
        kinds = [type(p).__name__ for p in follow_up.parts]
        assert "ToolReturnPart" in kinds
        assert "UserPromptPart" in kinds

    def test_orphan_call_placeholder_precedes_user_prompt_in_request(
        self,
    ) -> None:
        """Placeholder ToolReturnPart must come BEFORE UserPromptPart.

        Regression: pydantic-ai's OpenAI mapper walks ``ModelRequest.parts``
        in order and emits one wire message per part. If the placeholder is
        appended after an existing ``UserPromptPart`` the emitted sequence
        is ``assistant(tool_calls=[c1]) → user → tool``, which OpenAI rejects
        because the ``tool`` role message must *immediately* follow the
        ``assistant`` message whose ``tool_calls`` carry its ``tool_call_id``.
        """
        existing = [_user("hi"), _assistant(_tool_call("c1"))]
        new = [_user("follow-up")]
        result = append_messages_safely(existing, new)
        follow_up = result[2]
        assert isinstance(follow_up, ModelRequest)
        tool_return_idx = next(
            (
                i
                for i, p in enumerate(follow_up.parts)
                if isinstance(p, ToolReturnPart)
            ),
            None,
        )
        user_prompt_idx = next(
            (
                i
                for i, p in enumerate(follow_up.parts)
                if isinstance(p, UserPromptPart)
            ),
            None,
        )
        assert tool_return_idx is not None
        assert user_prompt_idx is not None
        assert tool_return_idx < user_prompt_idx, (
            "ToolReturnPart must precede UserPromptPart; got parts "
            f"{[type(p).__name__ for p in follow_up.parts]}"
        )

    def test_orphan_call_placeholder_precedes_system_and_user_prompts(
        self,
    ) -> None:
        """Placeholder must come before every SystemPromptPart/UserPromptPart.

        Same adjacency rule as the user-prompt case: a SystemPromptPart
        between the ``assistant(tool_calls)`` message and the placeholder
        ``tool`` message also breaks OpenAI's pairing requirement.
        """
        existing = [_user("hi"), _assistant(_tool_call("c1"))]
        new = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content="be concise"),
                    UserPromptPart(content="follow-up"),
                ],
            ),
        ]
        result = append_messages_safely(existing, new)
        follow_up = result[2]
        assert isinstance(follow_up, ModelRequest)
        # The first part MUST be the synthetic ToolReturnPart so it maps to
        # the adjacent `tool` message on the wire.
        first = follow_up.parts[0]
        assert isinstance(first, ToolReturnPart)
        assert first.tool_call_id == "c1"

    def test_mixed_orphans_both_fixed(self) -> None:
        """Simultaneously drop orphan returns and pair orphan calls."""
        existing = [
            _user("hi"),
            _assistant(_tool_call("paired")),
            _tool_return("paired"),
            _assistant(_tool_call("lonely")),  # never answered
        ]
        new = [_tool_return("ghost")]  # matches no call
        result = append_messages_safely(existing, new)
        call_ids = {
            p.tool_call_id
            for m in result
            for p in m.parts
            if isinstance(p, ToolCallPart)
        }
        return_ids = {
            p.tool_call_id
            for m in result
            for p in m.parts
            if isinstance(p, ToolReturnPart)
        }
        assert call_ids == return_ids  # every call paired, no orphan returns
        assert "ghost" not in return_ids
        assert "lonely" in return_ids  # placeholder added

    def test_partial_orphan_return_leaves_other_parts_intact(self) -> None:
        """Dropping an orphan return doesn't remove co-located parts."""
        # A ModelRequest can carry a user prompt AND a tool return together.
        existing = [
            _user("hi"),
            _assistant(_tool_call("c1")),
        ]
        mixed_request = ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="ghost", content="x", tool_call_id="ghost",
                ),
                UserPromptPart(content="hello again"),
            ],
        )
        new = [mixed_request]
        result = append_messages_safely(existing, new)
        # The ghost return is gone, but the user prompt survives — AND the
        # orphan call c1 got its placeholder appended to the same request.
        survivors = result[-1]
        assert isinstance(survivors, ModelRequest)
        part_types = [type(p).__name__ for p in survivors.parts]
        assert "UserPromptPart" in part_types
        return_ids = {
            p.tool_call_id
            for p in survivors.parts
            if isinstance(p, ToolReturnPart)
        }
        assert "ghost" not in return_ids
        assert "c1" in return_ids

    def test_empty_inputs_return_empty(self) -> None:
        assert append_messages_safely([], []) == []
