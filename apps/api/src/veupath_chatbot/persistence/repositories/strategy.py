"""Strategy repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import Strategy, StrategyHistory
from veupath_chatbot.platform.types import JSONArray, JSONObject


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
        plan: JSONObject,
        steps: JSONArray | None = None,
        root_step_id: str | None = None,
        wdk_strategy_id: int | None = None,
        strategy_id: UUID | None = None,
        title: str | None = None,
        is_saved: bool = False,
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
            # When plan is present/valid we derive steps at read-time,
            # but we also support snapshot-only persistence (steps/root without plan).
            steps=steps or [],
            root_step_id=root_step_id,
            wdk_strategy_id=wdk_strategy_id,
            is_saved=is_saved,
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
        plan: JSONObject | None = None,
        steps: JSONArray | None = None,
        root_step_id: str | None = None,
        root_step_id_set: bool = False,
        wdk_strategy_id: int | None = None,
        wdk_strategy_id_set: bool = False,
        result_count: int | None = None,
        record_type: str | None = None,
        messages: JSONArray | None = None,
        thinking: JSONObject | None = None,
        is_saved: bool | None = None,
        is_saved_set: bool = False,
        model_id: str | None = None,
        model_id_set: bool = False,
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
            # plan-only persistence: always clear derived fields on save
            strategy.steps = []
            strategy.root_step_id = None
        # Snapshot-only persistence: allow storing derived steps/root without requiring a plan.
        if steps is not None:
            strategy.steps = steps
        if root_step_id_set:
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
        if is_saved_set:
            strategy.is_saved = bool(is_saved)
        if model_id_set:
            strategy.model_id = model_id
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

    async def prune_wdk_orphans(
        self,
        user_id: UUID,
        site_id: str,
        live_wdk_ids: set[int],
    ) -> int:
        """Delete local strategies whose WDK counterpart no longer exists.

        :param user_id: Owner.
        :param site_id: Site to scope the pruning.
        :param live_wdk_ids: Set of WDK strategy IDs that still exist.
        :returns: Number of pruned rows.
        """
        # Find local strategies linked to WDK but not in the live set.
        stmt = select(Strategy).where(
            Strategy.user_id == user_id,
            Strategy.site_id == site_id,
            Strategy.wdk_strategy_id.isnot(None),
        )
        result = await self.session.execute(stmt)
        orphans = [
            s
            for s in result.scalars().all()
            if s.wdk_strategy_id is not None and s.wdk_strategy_id not in live_wdk_ids
        ]
        for orphan in orphans:
            await self.session.delete(orphan)
        return len(orphans)

    async def add_message(
        self, strategy_id: UUID, message: JSONObject
    ) -> Strategy | None:
        """Add a message to the strategy chat."""
        strategy = await self.get_by_id(strategy_id)
        if strategy is None:
            return None
        strategy.messages = [*(strategy.messages or []), message]
        await self.session.flush()
        return strategy

    async def update_thinking(
        self, strategy_id: UUID, thinking: JSONObject | None
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
