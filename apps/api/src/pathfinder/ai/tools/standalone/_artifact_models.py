"""Artifact tool response models."""

from __future__ import annotations

from pathfinder.platform.pydantic_base import CamelModel


class ConversationTitleResult(CamelModel):
    """Result of setting the conversation title."""

    conversation_title: str
