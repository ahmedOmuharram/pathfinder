"""Typed payload for conversation-title data-part.

Emitted by the title-proposing tool. The frontend reads this and copies
`title` into ``message.metadata.conversationTitle`` via a data-part
renderer with a side-effect (see plan Task 4c.9, option (b)).
"""

from __future__ import annotations

from shared_py.pydantic_base import CamelModel


class ConversationTitle(CamelModel):
    """A proposed short title for the conversation."""

    title: str
