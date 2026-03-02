"""Shared fake repository classes for processor tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID


class FakeSession:
    """Fake SQLAlchemy session for tracking commit calls."""

    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeStrategyRepo:
    """Fake StrategyRepository for ChatStreamProcessor tests."""

    def __init__(self) -> None:
        self.session = FakeSession()
        self.updated: list[dict] = []
        self.created: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.thinking_updates: list[dict[str, Any]] = []
        self.thinking_cleared: list[UUID] = []

    async def update(self, strategy_id: UUID, **kwargs):
        self.updated.append({"strategy_id": strategy_id, **kwargs})
        return SimpleNamespace(id=strategy_id)

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return None

    async def update_thinking(self, strategy_id: UUID, payload: dict[str, Any]):
        self.thinking_updates.append(payload)

    async def clear_thinking(self, strategy_id: UUID):
        self.thinking_cleared.append(strategy_id)

    async def add_message(self, strategy_id: UUID, message: dict[str, Any]):
        self.messages.append(message)
