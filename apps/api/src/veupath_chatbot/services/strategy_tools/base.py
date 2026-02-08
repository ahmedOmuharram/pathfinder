"""Shared base class for strategy tool implementations (service layer)."""

from __future__ import annotations

from veupath_chatbot.services.strategy_session import StrategySession


class StrategyToolsBase:
    """Base strategy tools class with shared state."""

    def __init__(self, session: StrategySession) -> None:
        self.session = session
