"""Repository layer for database operations."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import Strategy, StrategyHistory, User


class UserRepository:
    """User CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        return await self.session.get(User, user_id)

    async def get_or_create(self, user_id: UUID) -> User:
        """Get existing user or create new one."""
        user = await self.get_by_id(user_id)
        if user is None:
            user = User(id=user_id)
            self.session.add(user)
            await self.session.flush()
        return user

    async def create(self, external_id: str | None = None) -> User:
        """Create a new user."""
        user = User(external_id=external_id)
        self.session.add(user)
        await self.session.flush()
        return user


class StrategyRepository:
    """Strategy CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, strategy_id: UUID) -> Strategy | None:
        """Get strategy by ID."""
        return await self.session.get(Strategy, strategy_id)

    async def list_by_user(
        self, user_id: UUID, site_id: str | None = None, limit: int = 50
    ) -> list[Strategy]:
        """List strategies for a user."""
        stmt = (
            select(Strategy)
            .where(Strategy.user_id == user_id)
            .order_by(Strategy.updated_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Strategy.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_wdk_strategy_id(
        self, user_id: UUID, wdk_strategy_id: int
    ) -> Strategy | None:
        """Get strategy by WDK strategy ID for a user."""
        stmt = select(Strategy).where(
            Strategy.user_id == user_id,
            Strategy.wdk_strategy_id == wdk_strategy_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        name: str,
        site_id: str,
        record_type: str | None,
        plan: dict[str, Any],
        steps: list[dict[str, Any]],
        root_step_id: str | None,
        wdk_strategy_id: int | None = None,
        strategy_id: UUID | None = None,
        title: str | None = None,
    ) -> Strategy:
        """Create a new strategy."""
        strategy = Strategy(
            id=strategy_id,
            user_id=user_id,
            name=name,
            title=title,
            site_id=site_id,
            record_type=record_type,
            plan=plan,
            steps=steps,
            root_step_id=root_step_id,
            wdk_strategy_id=wdk_strategy_id,
        )
        self.session.add(strategy)
        await self.session.flush()

        # Create initial history entry
        history = StrategyHistory(
            strategy_id=strategy.id,
            version=1,
            plan=plan,
            description="Initial creation",
        )
        self.session.add(history)
        await self.session.flush()

        return strategy

    async def update(
        self,
        strategy_id: UUID,
        name: str | None = None,
        title: str | None = None,
        plan: dict[str, Any] | None = None,
        steps: list[dict[str, Any]] | None = None,
        root_step_id: str | None = None,
        wdk_strategy_id: int | None = None,
        wdk_strategy_id_set: bool = False,
        result_count: int | None = None,
        record_type: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        thinking: dict[str, Any] | None = None,
    ) -> Strategy | None:
        """Update a strategy."""
        strategy = await self.get_by_id(strategy_id)
        if strategy is None:
            return None

        if name is not None:
            strategy.name = name
        if title is not None:
            strategy.title = title
        if plan is not None:
            strategy.plan = plan
        if steps is not None:
            strategy.steps = steps
        if root_step_id is not None:
            strategy.root_step_id = root_step_id
        if wdk_strategy_id_set:
            strategy.wdk_strategy_id = wdk_strategy_id
        if result_count is not None:
            strategy.result_count = result_count
        if record_type is not None:
            strategy.record_type = record_type
        if messages is not None:
            strategy.messages = messages
        if thinking is not None:
            strategy.thinking = thinking
        await self.session.flush()

        # Create history entry if plan changed
        if plan is not None:
            # Get latest version
            stmt = (
                select(StrategyHistory)
                .where(StrategyHistory.strategy_id == strategy_id)
                .order_by(StrategyHistory.version.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            latest = result.scalar_one_or_none()
            version = (latest.version + 1) if latest else 1

            history = StrategyHistory(
                strategy_id=strategy_id,
                version=version,
                plan=plan,
                description="Updated",
            )
            self.session.add(history)
            await self.session.flush()

        return strategy

    async def delete(self, strategy_id: UUID) -> bool:
        """Delete a strategy."""
        strategy = await self.get_by_id(strategy_id)
        if strategy is None:
            return False
        await self.session.delete(strategy)
        return True

    async def add_message(
        self, strategy_id: UUID, message: dict[str, Any]
    ) -> Strategy | None:
        """Add a message to the strategy chat."""
        strategy = await self.get_by_id(strategy_id)
        if strategy is None:
            return None
        strategy.messages = [*(strategy.messages or []), message]
        await self.session.flush()
        return strategy

    async def update_thinking(
        self, strategy_id: UUID, thinking: dict[str, Any] | None
    ) -> Strategy | None:
        """Update in-progress thinking payload."""
        strategy = await self.get_by_id(strategy_id)
        if strategy is None:
            return None
        strategy.thinking = thinking
        await self.session.flush()
        return strategy

    async def clear_thinking(self, strategy_id: UUID) -> Strategy | None:
        """Clear in-progress thinking payload."""
        return await self.update_thinking(strategy_id, None)

    async def refresh(self, strategy: Strategy) -> None:
        """Refresh a strategy instance from the database."""
        await self.session.refresh(strategy)

    async def get_history(
        self, strategy_id: UUID, limit: int = 20
    ) -> list[StrategyHistory]:
        """Get version history for a strategy."""
        stmt = (
            select(StrategyHistory)
            .where(StrategyHistory.strategy_id == strategy_id)
            .order_by(StrategyHistory.version.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


