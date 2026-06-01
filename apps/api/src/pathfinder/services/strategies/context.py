"""Narrow context for strategy-mutation services.

The strategy build/commit/persist services need only a strategy session,
a site id, and (for persistence) a conversation id + DB session factory —
not the full AI ``AgentDeps`` container. Depending on this narrow context
keeps the service layer free of any AI-layer import.
"""

from dataclasses import dataclass
from uuid import UUID

from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.db import DBSessionFactory


@dataclass(frozen=True)
class StrategyMutationContext:
    site_id: str
    strategy_session: StrategySession
    conversation_id: UUID | None = None
    db_session_factory: DBSessionFactory | None = None
