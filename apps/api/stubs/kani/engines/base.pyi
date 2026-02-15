"""Type stub for kani.engines.base - provides proper types for BaseEngine.

The kani package does not ship with inline types or py.typed stubs, so mypy
infers BaseEngine as Any. This stub provides the correct interface so
ScriptedKaniEngine and other subclasses type-check correctly.
"""

from collections.abc import AsyncIterable
from typing import Any

from kani.ai_function import AIFunction
from kani.models import ChatMessage

class BaseCompletion:
    """Base class for all LM engine completions."""

    @property
    def message(self) -> ChatMessage: ...
    @property
    def prompt_tokens(self) -> int | None: ...
    @property
    def completion_tokens(self) -> int | None: ...

class Completion(BaseCompletion):
    """Concrete completion implementation."""

    def __init__(
        self,
        message: ChatMessage,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None: ...

class BaseEngine:
    """Base class for all LM engines."""

    max_context_size: int

    def prompt_len(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **kwargs: Any,
    ) -> int: ...
    async def predict(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **hyperparams: Any,
    ) -> BaseCompletion: ...
    def stream(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction] | None = None,
        **hyperparams: Any,
    ) -> AsyncIterable[str | BaseCompletion]: ...
    async def close(self) -> None: ...
