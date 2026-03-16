"""Type stub for kani.kani — the core Kani agent class."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from kani.ai_function import AIFunction
from kani.engines.base import BaseEngine
from kani.internal import FunctionCallResult
from kani.models import ChatMessage, ChatRole, FunctionCall

class Completion:
    prompt_tokens: int | None
    completion_tokens: int | None
    def __init__(self, **kwargs: Any) -> None: ...

class StreamManager:
    """Async iterator for streaming tokens, with metadata accessors."""

    role: ChatRole

    def __aiter__(self) -> AsyncIterator[str]: ...
    async def __anext__(self) -> str: ...
    async def message(self) -> ChatMessage: ...
    async def completion(self) -> Completion: ...

class Kani:
    """Base class for kani agents."""

    chat_history: list[ChatMessage]
    engine: BaseEngine
    functions: dict[str, AIFunction]
    event_queue: Any

    def __init__(
        self,
        engine: BaseEngine,
        system_prompt: str | None = None,
        always_included_messages: list[ChatMessage] | None = None,
        desired_response_tokens: int | None = None,
        chat_history: list[ChatMessage] | None = None,
        functions: list[AIFunction] | None = None,
        retry_attempts: int = 1,
    ) -> None: ...
    async def chat_round(
        self,
        query: str | Sequence[Any] | None,
        **kwargs: Any,
    ) -> ChatMessage: ...
    async def chat_round_str(
        self,
        query: str | Sequence[Any] | None,
        **kwargs: Any,
    ) -> str: ...
    def full_round(
        self,
        query: str | Sequence[Any] | None,
        *,
        max_function_rounds: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatMessage]: ...
    def full_round_str(
        self,
        query: str | Sequence[Any] | None,
        **kwargs: Any,
    ) -> AsyncIterator[str]: ...
    def full_round_stream(
        self,
        query: str | Sequence[Any] | None,
        *,
        max_function_rounds: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamManager]: ...
    async def do_function_call(
        self,
        call: FunctionCall,
        tool_call_id: str | None = None,
    ) -> FunctionCallResult: ...
