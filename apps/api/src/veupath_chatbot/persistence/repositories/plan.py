"""Repository for strategy plan persistence."""

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.domain.strategy.plan import StrategyPlan
from veupath_chatbot.persistence.models import StrategyPlanRecord
from veupath_chatbot.platform.types import JSONObject


class PlanRepository:
    """Data access for strategy plans."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_plan(self, plan: StrategyPlan, stream_id: UUID) -> None:
        """Upsert a strategy plan record for the given stream."""
        record = StrategyPlanRecord(
            id=plan.id,
            stream_id=stream_id,
            status=plan.status.value,
            plan_json=plan.model_dump(by_alias=True, mode="json"),
        )
        await self.session.merge(record)
        await self.session.flush()

    async def get_active_plan(self, stream_id: UUID) -> StrategyPlan | None:
        """Return the most-recently-updated non-terminal plan for a stream."""
        stmt = (
            select(StrategyPlanRecord)
            .where(
                StrategyPlanRecord.stream_id == stream_id,
                StrategyPlanRecord.status.in_(
                    ["draft", "presented", "approved", "executing"]
                ),
            )
            .order_by(StrategyPlanRecord.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return StrategyPlan.model_validate(record.plan_json)

    async def update_plan_status(
        self,
        plan_id: str,
        status: str,
        plan_json: JSONObject | None = None,
    ) -> None:
        """Update status (and optionally the full JSON) for a plan."""
        values: dict[str, Any] = {"status": status}
        if plan_json is not None:
            values["plan_json"] = plan_json
        stmt = (
            update(StrategyPlanRecord)
            .where(StrategyPlanRecord.id == plan_id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.flush()
