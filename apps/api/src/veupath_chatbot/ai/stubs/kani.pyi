"""Type stub for kani.Kani to help mypy understand it's a valid base class."""

from typing import Any

from kani.ai_function import AIFunction
from kani.engines.base import BaseEngine
from kani.models import ChatMessage

class Kani:
    """Type stub for kani.Kani base class."""

    chat_history: list[ChatMessage]

    def __init__(
        self,
        engine: BaseEngine,
        system_prompt: str | None = None,
        always_included_messages: list[ChatMessage] | None = None,
        desired_response_tokens: int | None = None,
        chat_history: list[ChatMessage] | None = None,
        functions: list[AIFunction] | None = None,
        retry_attempts: int = 1,
        **kwargs: Any,
    ) -> None:
        """Initialize a Kani agent."""
        ...
