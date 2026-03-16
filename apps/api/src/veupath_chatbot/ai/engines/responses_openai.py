"""OpenAI engine that uses Responses API without forcing encrypted reasoning.

Kani's OpenAIEngine unconditionally adds ``include=["reasoning.encrypted_content"]``
for all Responses API calls, but non-reasoning models (gpt-4.1, gpt-4.1-mini,
gpt-4.1-nano) reject this parameter.  This subclass strips it for those models.
"""

from typing import Any

from kani import AIFunction, ChatMessage
from kani.engines.openai import OpenAIEngine

# Models whose prefix indicates they support reasoning encrypted content.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


class ResponsesOpenAIEngine(OpenAIEngine):
    """OpenAIEngine that always uses the Responses API.

    Strips ``reasoning.encrypted_content`` from the ``include`` parameter
    for models that don't support reasoning, preventing 400 errors.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("api_type", "responses")
        super().__init__(*args, **kwargs)
        self._supports_reasoning: bool = any(
            self.model.startswith(p) for p in _REASONING_PREFIXES
        )

    def _prepare_request(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction],
        **kwargs: Any,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
        kwargs, translated, tools = super()._prepare_request(
            messages, functions, **kwargs
        )
        if not self._supports_reasoning:
            include = kwargs.get("include")
            if isinstance(include, list) and "reasoning.encrypted_content" in include:
                include.remove("reasoning.encrypted_content")
                if not include:
                    kwargs.pop("include", None)
        return kwargs, translated, tools
