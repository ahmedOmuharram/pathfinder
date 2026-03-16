"""Type stub for kani.models."""

from enum import Enum
from typing import Any

class ChatRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"

class FunctionCall:
    name: str
    arguments: str

class ToolCall:
    id: str
    type: str
    function: FunctionCall

    @classmethod
    def from_function(
        cls, __name: str, /, *, call_id_: str | None = None, **kwargs: Any
    ) -> ToolCall: ...

class ChatMessage:
    role: ChatRole
    content: str | None
    name: str | None
    function_call: FunctionCall | None
    tool_call_id: str | None
    tool_calls: list[ToolCall] | None
    text: str
    extra: dict[str, Any]

    def __init__(self, **kwargs: Any) -> None: ...
    @classmethod
    def system(cls, content: str, **kwargs: Any) -> ChatMessage: ...
    @classmethod
    def user(cls, content: str, **kwargs: Any) -> ChatMessage: ...
    @classmethod
    def assistant(cls, content: str | None = None, **kwargs: Any) -> ChatMessage: ...
    @classmethod
    def function(
        cls, name: str, content: str, tool_call_id: str | None = None, **kwargs: Any
    ) -> ChatMessage: ...
    def copy_with(self, **kwargs: Any) -> ChatMessage: ...
