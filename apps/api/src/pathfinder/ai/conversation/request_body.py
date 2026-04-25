from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    UIMessagePart,
)

from pathfinder.platform.pydantic_base import CamelModel


class UIMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    role: Literal["system", "user", "assistant"]
    parts: list[UIMessagePart] = Field(default_factory=list)


class ChatRequestBody(CamelModel):
    """Typed body for ``POST /api/v1/chat`` (AI SDK v6 + PathFinder extras).

    The shape matches ``@ai-sdk/react``'s ``useChat`` submit payload
    (``trigger``, ``id``, ``messages``) with PathFinder-scoped fields
    (``conversationId``, ``siteId``, ``mode``, ``experimentId``) layered on
    via ``body`` on the client transport. The authenticated user UUID still
    comes from the ``pathfinder-auth`` cookie.
    """

    model_config = ConfigDict(extra="ignore")

    trigger: Literal["submit-message", "regenerate-message"] = "submit-message"
    id: str = ""
    messages: list[UIMessage] = Field(default_factory=list)

    conversation_id: UUID
    site_id: str = ""
    mode: str = "strategy"
    experiment_id: str | None = None

    @property
    def last_user_text(self) -> str:
        """Extract the concatenated text of the last user message's parts."""
        if not self.messages:
            return ""
        last = self.messages[-1]
        if last.role != "user":
            return ""
        return "".join(
            part.text
            for part in last.parts
            if isinstance(part, TextUIPart) and part.text
        )

    @property
    def last_user_message_id(self) -> UUID:
        if not self.messages or self.messages[-1].role != "user":
            msg = "ChatRequestBody.messages must end with a user message"
            raise ValueError(msg)
        return UUID(self.messages[-1].id)
