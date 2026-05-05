from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field
from pydantic_ai.ui.vercel_ai._utils import iter_tool_approval_responses
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    UIMessage,
)

from pathfinder.platform.pydantic_base import CamelModel


class ChatRequestBody(CamelModel):
    """Typed body for ``POST /api/v1/chat`` (AI SDK v6 + PathFinder extras).

    The shape matches ``@ai-sdk/react``'s ``useChat`` submit payload
    (``trigger``, ``id``, ``messages``) with PathFinder-scoped fields
    (``conversationId``, ``siteId``, ``mode``, ``experimentId``) layered on
    via ``body`` on the client transport. The authenticated user UUID still
    comes from the ``pathfinder-auth`` cookie. ``messages`` uses pydantic-ai's
    ``UIMessage`` so deferred-tool approval-responded parts deserialize into
    the discriminated union and ``iter_tool_approval_responses`` works.
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

    @property
    def is_approval_resume(self) -> bool:
        """True when this turn is the user's structured approve/deny click.

        SDK v6 fires a chat POST automatically (via ``sendAutomaticallyWhen``)
        after ``addToolApprovalResponse``; the request carries the assistant
        message with the ``approval-responded`` part instead of a new user
        message.
        """
        return any(True for _ in iter_tool_approval_responses(self.messages))

    @property
    def prior_assistant_message_id(self) -> UUID | None:
        if not self.is_approval_resume:
            return None
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return UUID(msg.id)
        return None
