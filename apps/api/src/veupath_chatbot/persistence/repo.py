"""Repository layer for database operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import (
    PlanSession,
    Strategy,
    StrategyHistory,
    User,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject


class UserRepository:
    """User CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        return await self.session.get(User, user_id)

    async def get_or_create(self, user_id: UUID) -> User:
        """Get existing user or create new one."""
        # Avoid race conditions when multiple concurrent requests attempt to create
        # the same user (e.g. initial page load triggering parallel API calls).
        stmt = (
            pg_insert(User)
            .values(id=user_id)
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        await self.session.execute(stmt)
        user = await self.get_by_id(user_id)
        if user is None:
            # Should be impossible, but keep behavior explicit.
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
        plan: JSONObject,
        steps: JSONArray | None = None,
        root_step_id: str | None = None,
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
            # When plan is present/valid we derive steps at read-time,
            # but we also support snapshot-only persistence (steps/root without plan).
            steps=steps or [],
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


class PlanSessionRepository:
    """Plan session CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, plan_session_id: UUID) -> PlanSession | None:
        return await self.session.get(PlanSession, plan_session_id)

    async def get_by_id_for_user(
        self, *, plan_session_id: UUID, user_id: UUID
    ) -> PlanSession | None:
        stmt = select(PlanSession).where(
            PlanSession.id == plan_session_id, PlanSession.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, site_id: str | None = None, limit: int = 50
    ) -> list[PlanSession]:
        stmt = (
            select(PlanSession)
            .where(PlanSession.user_id == user_id)
            .order_by(PlanSession.updated_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(PlanSession.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        user_id: UUID,
        site_id: str,
        title: str = "Plan",
        plan_session_id: UUID | None = None,
    ) -> PlanSession:
        ps = PlanSession(
            id=plan_session_id,
            user_id=user_id,
            site_id=site_id,
            title=title,
            messages=[],
            planning_artifacts=[],
            thinking=None,
        )
        self.session.add(ps)
        await self.session.flush()
        return ps

    async def add_message(
        self, plan_session_id: UUID, message: JSONObject
    ) -> PlanSession | None:
        ps = await self.get_by_id(plan_session_id)
        if ps is None:
            return None
        ps.messages = [*(ps.messages or []), message]
        await self.session.flush()
        return ps

    async def update_thinking(
        self, plan_session_id: UUID, thinking: JSONObject | None
    ) -> PlanSession | None:
        ps = await self.get_by_id(plan_session_id)
        if ps is None:
            return None
        ps.thinking = thinking
        await self.session.flush()
        return ps

    async def clear_thinking(self, plan_session_id: UUID) -> PlanSession | None:
        return await self.update_thinking(plan_session_id, None)

    async def append_planning_artifacts(
        self, plan_session_id: UUID, artifacts: JSONArray
    ) -> PlanSession | None:
        ps = await self.get_by_id(plan_session_id)
        if ps is None:
            return None
        existing = ps.planning_artifacts or []
        incoming = [a for a in (artifacts or []) if isinstance(a, dict)]
        if not incoming:
            return ps

        # Upsert by artifact id (so "draft" artifacts can be updated without duplication).
        by_id: dict[str, JSONObject] = {}
        ordered: JSONArray = []
        for a in existing:
            if not isinstance(a, dict):
                continue
            aid = a.get("id")
            if isinstance(aid, str) and aid:
                by_id[aid] = a
            ordered.append(a)

        for a in incoming:
            aid = a.get("id")
            if isinstance(aid, str) and aid and aid in by_id:
                # Replace in the ordered list at the original position.
                for i, old in enumerate(ordered):
                    if isinstance(old, dict) and old.get("id") == aid:
                        ordered[i] = a
                        break
                by_id[aid] = a
            else:
                ordered.append(a)
                if isinstance(aid, str) and aid:
                    by_id[aid] = a

        ps.planning_artifacts = ordered
        await self.session.flush()
        return ps

    async def refresh(self, plan_session: PlanSession) -> None:
        await self.session.refresh(plan_session)

    async def delete(self, *, plan_session_id: UUID, user_id: UUID) -> bool:
        ps = await self.get_by_id_for_user(
            plan_session_id=plan_session_id, user_id=user_id
        )
        if ps is None:
            return False
        await self.session.delete(ps)
        return True

    async def update_title(
        self, *, plan_session_id: UUID, user_id: UUID, title: str
    ) -> PlanSession | None:
        ps = await self.get_by_id_for_user(
            plan_session_id=plan_session_id, user_id=user_id
        )
        if ps is None:
            return None
        ps.title = title
        await self.session.flush()
        # Ensure server-side fields (e.g. updated_at) are populated and not expired.
        await self.session.refresh(ps)
        return ps
