"""Type stub for kani.engines.anthropic."""

from typing import Any

from kani.ai_function import AIFunction
from kani.engines.base import BaseEngine
from kani.models import ChatMessage

class AnthropicEngine(BaseEngine):
    model: str
    def __init__(self, api_key: str, model: str, **kwargs: Any) -> None: ...
    @staticmethod
    def _prepare_request(
        messages: list[ChatMessage],
        functions: list[AIFunction],
        *,
        intent: str = "create",
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]: ...
