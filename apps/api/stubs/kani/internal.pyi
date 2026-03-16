"""Type stub for kani.internal."""

from kani.models import ChatMessage

class FunctionCallResult:
    is_model_turn: bool
    message: ChatMessage

    def __init__(
        self, is_model_turn: bool = True, message: ChatMessage | None = None
    ) -> None: ...
