"""Control set repository."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import ControlSet


class ControlSetRepository:
    """Control set CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, control_set_id: UUID) -> ControlSet | None:
        """Get control set by ID."""
        return await self.session.get(ControlSet, control_set_id)

    async def list_by_site(
        self,
        site_id: str,
        user_id: UUID | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
    ) -> list[ControlSet]:
        """List control sets for a site, including public ones and user-owned."""
        conditions = [ControlSet.site_id == site_id]
        if user_id is not None:
            conditions.append(
                or_(ControlSet.is_public.is_(True), ControlSet.user_id == user_id)
            )
        else:
            conditions.append(ControlSet.is_public.is_(True))

        stmt = (
            select(ControlSet)
            .where(*conditions)
            .order_by(ControlSet.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        if tags:
            tag_set = set(tags)
            rows = [
                r
                for r in rows
                if tag_set.intersection(r.tags if isinstance(r.tags, list) else [])
            ]
        return rows

    async def create(
        self,
        *,
        name: str,
        site_id: str,
        record_type: str,
        positive_ids: list[str],
        negative_ids: list[str],
        source: str | None = None,
        tags: list[str] | None = None,
        provenance_notes: str | None = None,
        is_public: bool = False,
        user_id: UUID | None = None,
    ) -> ControlSet:
        """Create a new control set."""
        cs = ControlSet(
            name=name,
            site_id=site_id,
            record_type=record_type,
            positive_ids=positive_ids,
            negative_ids=negative_ids,
            source=source,
            tags=tags or [],
            provenance_notes=provenance_notes,
            is_public=is_public,
            user_id=user_id,
        )
        self.session.add(cs)
        await self.session.flush()
        return cs

    async def delete(self, control_set_id: UUID) -> bool:
        """Delete a control set."""
        cs = await self.get_by_id(control_set_id)
        if cs is None:
            return False
        await self.session.delete(cs)
        return True
