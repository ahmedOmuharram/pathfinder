"""Type stub for kani.engines.openai."""

from typing import Any

from kani.ai_function import AIFunction
from kani.engines.base import BaseEngine
from kani.models import ChatMessage

class OpenAIEngine(BaseEngine):
    model: str
    def __init__(self, api_key: str = ..., model: str = ..., **kwargs: Any) -> None: ...
    def _prepare_request(
        self,
        messages: list[ChatMessage],
        functions: list[AIFunction],
        *,
        intent: str = ...,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]: ...
