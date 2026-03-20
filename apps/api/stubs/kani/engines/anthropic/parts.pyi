"""Type stub for kani.engines.anthropic.parts."""

from typing import Any

from kani.models import MessagePart

class AnthropicThinkingPart(MessagePart):
    content: str | None
    signature: str | None
    def __init__(
        self, *, content: str | None = None, signature: str | None = None
    ) -> None: ...

class AnthropicUnknownPart(MessagePart):
    type: str
    data: dict[str, Any]
    def __init__(self, *, type: str, data: dict[str, Any]) -> None: ...  # noqa: A002
