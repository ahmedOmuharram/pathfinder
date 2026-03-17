"""Anthropic engine with prompt caching and thinking-block fixes."""

import json
import warnings
from typing import Any

from kani import AIFunction, ChatMessage
from kani.engines.anthropic import AnthropicEngine
from kani.engines.anthropic.parts import AnthropicThinkingPart, AnthropicUnknownPart
from kani.engines.base import Completion
from kani.models import FunctionCall, MessagePart, ToolCall


class CachedAnthropicEngine(AnthropicEngine):
    """AnthropicEngine subclass that adds prompt caching and fixes thinking blocks.

    Fixes:
    - Anthropic's prompt caching reduces cache-hit costs by 90%.
    - Wraps single-MessagePart content in a list to prevent Pydantic
      validation errors when the response is a bare thinking block.
    """

    @staticmethod
    def _prepare_request(
        messages: list[ChatMessage],
        functions: list[AIFunction],
        *,
        intent: str = "create",
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        kwargs, translated = AnthropicEngine._prepare_request(
            messages, functions, intent=intent
        )
        # Wrap the system prompt (a plain string) with cache_control.
        system_text = kwargs.get("system")
        if isinstance(system_text, str) and system_text:
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        return kwargs, translated

    def _translate_anthropic_message(self, message: Any) -> Completion:
        """Translate an Anthropic Message, fixing the bare-MessagePart bug.

        Upstream kani does ``content = parts[0] if len(parts) == 1 else parts``
        which produces a bare MessagePart when the response is a single thinking
        block.  ``ChatMessage.content`` expects ``str | list[...] | None``, so a
        bare MessagePart triggers a Pydantic ValidationError.

        This override reproduces the upstream logic but always wraps non-string
        single parts in a list.
        """
        tool_calls: list[ToolCall] = []
        parts: list[str | MessagePart] = []
        for part in message.content:
            if part.type == "text":
                parts.append(part.text)
            elif part.type == "tool_use":
                fc = FunctionCall(name=part.name, arguments=json.dumps(part.input))
                tc = ToolCall(id=part.id, type="function", function=fc)
                tool_calls.append(tc)
            elif part.type == "thinking":
                parts.append(
                    AnthropicThinkingPart(
                        content=part.thinking, signature=part.signature
                    )
                )
            else:
                parts.append(
                    AnthropicUnknownPart(type=part.type, data=part.model_dump())
                )
                warnings.warn(
                    f"Unknown Anthropic content block type: {part.type}",
                    stacklevel=2,
                )

        # Fix: only unwrap to a bare value when the single part is a plain string.
        # A bare MessagePart would fail Pydantic validation on ChatMessage.content.
        if len(parts) == 1 and isinstance(parts[0], str):
            content: str | list[str | MessagePart] = parts[0]
        else:
            content = parts

        kani_msg = ChatMessage.assistant(content, tool_calls=tool_calls or None)

        self.set_cached_message_len(kani_msg, message.usage.output_tokens)
        kani_msg.extra["anthropic_message"] = message

        return Completion(
            message=kani_msg,
            prompt_tokens=message.usage.input_tokens,
            completion_tokens=message.usage.output_tokens,
        )
