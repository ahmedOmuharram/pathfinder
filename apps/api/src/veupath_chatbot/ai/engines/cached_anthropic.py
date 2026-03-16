"""Anthropic engine with prompt caching via cache_control headers."""

from typing import Any

from kani import AIFunction, ChatMessage
from kani.engines.anthropic import AnthropicEngine


class CachedAnthropicEngine(AnthropicEngine):
    """AnthropicEngine subclass that adds cache_control to system messages.

    Anthropic's prompt caching reduces cache-hit costs by 90%.
    System prompts and tool definitions are identical across calls,
    making them ideal caching candidates.
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
