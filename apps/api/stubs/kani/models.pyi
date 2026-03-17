"""Type stub for kani.models."""

from collections.abc import Sequence
from enum import Enum
from typing import Any

class ChatRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"

class MessagePart:
    """Abstract base class for message parts."""

    ...

class FunctionCall:
    name: str
    arguments: str

    def __init__(self, *, name: str, arguments: str) -> None: ...
    @classmethod
    def with_args(cls, __name: str, /, **kwargs: Any) -> FunctionCall: ...

class ToolCall:
    id: str
    type: str
    function: FunctionCall

    def __init__(self, *, id: str, type: str, function: FunctionCall) -> None: ...
    @classmethod
    def from_function(
        cls, __name: str, /, *, call_id_: str | None = None, **kwargs: Any
    ) -> ToolCall: ...
    @classmethod
    def from_function_call(
        cls, call: FunctionCall, call_id_: str | None = None
    ) -> ToolCall: ...

class ChatMessage:
    role: ChatRole
    content: str | list[str | MessagePart] | None
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
    def assistant(
        cls,
        content: str | Sequence[MessagePart | str] | None = None,
        **kwargs: Any,
    ) -> ChatMessage: ...
    @classmethod
    def function(
        cls, name: str, content: str, tool_call_id: str | None = None, **kwargs: Any
    ) -> ChatMessage: ...
    def copy_with(self, **kwargs: Any) -> ChatMessage: ...
