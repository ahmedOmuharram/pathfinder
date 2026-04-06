"""Type stub for kani.ai_function."""

from collections.abc import Callable
from typing import Any

from kani.models import ChatRole

class AIParam:
    """Parameter annotation for AI functions."""

    def __init__(self, desc: str = "", **kwargs: Any) -> None: ...

class AIFunction:
    """Represents a function exposed to the AI."""

    name: str
    desc: str
    auto_truncate: int | None
    json_schema: dict[str, Any]
    after: ChatRole | str
    inner: Callable[..., Any]

    def __init__(self, inner: Callable[..., Any], **kwargs: Any) -> None: ...

def ai_function(
    *,
    name: str | None = None,
    desc: str | None = None,
    auto_truncate: int | None = None,
    after: ChatRole | str = "",
    hidden: bool = False,
    **kwargs: Any,
) -> Callable[..., Any]: ...
