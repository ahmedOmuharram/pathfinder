"""Artifact tool response models."""

from __future__ import annotations

from veupath_chatbot.platform.pydantic_base import CamelModel


class ConversationTitleResult(CamelModel):
    """Result of setting the conversation title."""

    conversation_title: str
