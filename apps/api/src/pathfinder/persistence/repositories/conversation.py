"""Data access for chat conversations: identity, strategy metadata, and the
conversation sidebar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import Conversation
from pathfinder.platform.context import calling_application


@dataclass
class ConversationUpdate:
    """Partial update payload for a ``Conversation``.

    Only non-None fields are written. A ``*_set=True`` flag writes its field
    even when the value is ``None``.
    """

    name: str | None = None
    record_type: str | None = None
    wdk_strategy_id: int | None = None
    wdk_strategy_id_set: bool = False
    is_saved: bool | None = None
    is_saved_set: bool = False
    strategy_ast: StrategyAst | None = None
    strategy_ast_set: bool = False
    step_count: int | None = None
    estimated_size: int | None = None
    estimated_size_set: bool = False
    gene_set_id: str | None = None
    gene_set_id_set: bool = False
    gene_set_auto_imported: bool | None = None
    imported_saved_strategy_ids: list[int] | None = None
    touch_updated_at: bool = True


_SIMPLE_FIELDS: tuple[str, ...] = (
    "record_type",
    "step_count",
    "gene_set_auto_imported",
)

_FLAGGED_FIELDS: tuple[tuple[str, str], ...] = (
    ("wdk_strategy_id_set", "wdk_strategy_id"),
    ("estimated_size_set", "estimated_size"),
    ("gene_set_id_set", "gene_set_id"),
    ("is_saved_set", "is_saved"),
)


def _collect_chat_values(upd: ConversationUpdate) -> dict[str, Any]:
    """Build the column-value dict from non-None and flagged fields."""
    values: dict[str, Any] = {}
    if upd.touch_updated_at:
        values["updated_at"] = datetime.now(UTC)

    for attr in _SIMPLE_FIELDS:
        val = getattr(upd, attr)
        if val is not None:
            values[attr] = val

    if upd.strategy_ast is not None:
        values["strategy_ast"] = upd.strategy_ast.model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )
    elif upd.strategy_ast_set:
        # An explicit clear writes NULL, which removes the stored strategy.
        values["strategy_ast"] = None

    if upd.imported_saved_strategy_ids is not None:
        values["imported_saved_strategy_ids"] = list(upd.imported_saved_strategy_ids)

    for flag, attr in _FLAGGED_FIELDS:
        if getattr(upd, flag):
            values[attr] = getattr(upd, attr)

    return values


class ConversationRepository:
    """Data access for chat conversations.

    Every listing is scoped to the user under the calling application; a
    lookup by id is not, because the ownership helpers decide that case.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _deduplicate_name(
        self,
        user_id: UUID,
        site_id: str,
        name: str,
        exclude_conversation_id: UUID | None = None,
    ) -> str:
        """Return a unique chat name for the user and site. A taken name gets
        a numeric suffix."""
        query = select(Conversation.name).where(
            Conversation.user_id == user_id,
            Conversation.application_id == calling_application(),
            Conversation.site_id == site_id,
        )
        if exclude_conversation_id is not None:
            query = query.where(Conversation.id != exclude_conversation_id)
        result = await self.session.execute(query)
        existing: set[str] = {row[0] for row in result.all() if row[0]}

        if name not in existing:
            return name

        i = 1
        while f"{name} ({i})" in existing:
            i += 1
        return f"{name} ({i})"

    async def create(
        self,
        user_id: UUID,
        site_id: str,
        *,
        conversation_id: UUID | None = None,
        name: str = "",
    ) -> Conversation:
        """Create a chat with a deduplicated name. Callers can supply the id so
        the client and the server use the same value."""
        resolved_name = await self._deduplicate_name(
            user_id,
            site_id,
            name or DEFAULT_STREAM_NAME,
        )
        conversation = Conversation(
            id=conversation_id or uuid4(),
            user_id=user_id,
            site_id=site_id,
            name=resolved_name,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_strategy_lock(
        self, conversation_id: UUID
    ) -> Conversation | None:
        # The advisory lock releases at transaction end and does not block
        # concurrent reads of the row.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"strategy:{conversation_id}"},
        )
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def delete(
        self,
        conversation_id: UUID,
        *,
        cascade: bool = False,
    ) -> None:
        """Delete a conversation.

        Without ``cascade`` the direct children move up to the deleted node's
        parent. With ``cascade`` the whole subtree goes.
        """
        if cascade:
            sql = text(
                """
                WITH RECURSIVE descendants(id) AS (
                    SELECT id FROM conversations WHERE id = :id
                    UNION ALL
                    SELECT c.id FROM conversations c
                    JOIN descendants d ON c.parent_conversation_id = d.id
                )
                DELETE FROM conversations WHERE id IN (SELECT id FROM descendants)
                """,
            )
            await self.session.execute(sql, {"id": str(conversation_id)})
            await self.session.flush()
            return

        deleted = await self.session.scalar(
            select(Conversation).where(Conversation.id == conversation_id),
        )
        if deleted is not None:
            await self.session.execute(
                update(Conversation)
                .where(Conversation.parent_conversation_id == conversation_id)
                .values(
                    parent_conversation_id=deleted.parent_conversation_id,
                    parent_message_id=deleted.parent_message_id,
                ),
            )
        await self.session.execute(
            delete(Conversation).where(Conversation.id == conversation_id),
        )
        await self.session.flush()

    async def list_conversations(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[Conversation]:
        """List chats that are not dismissed, most recently updated first."""
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.application_id == calling_application())
            .where(Conversation.dismissed_at.is_(None))
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Conversation.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_dismissed_conversations(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.application_id == calling_application())
            .where(Conversation.dismissed_at.is_not(None))
            .order_by(Conversation.dismissed_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Conversation.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_wdk_strategy_id(
        self, user_id: UUID, wdk_strategy_id: int
    ) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.application_id == calling_application(),
                Conversation.wdk_strategy_id == wdk_strategy_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_consumers_per_saved_strategy(
        self,
        user_id: UUID,
        site_id: str,
    ) -> dict[int, int]:
        """Return the consumer count for each saved WDK strategy id."""
        result = await self.session.execute(
            select(Conversation.imported_saved_strategy_ids).where(
                Conversation.user_id == user_id,
                Conversation.application_id == calling_application(),
                Conversation.site_id == site_id,
                Conversation.dismissed_at.is_(None),
            ),
        )
        counts: dict[int, int] = {}
        for (ids,) in result.all():
            for sid in ids or []:
                if isinstance(sid, int):
                    counts[sid] = counts.get(sid, 0) + 1
        return counts

    async def list_consumers_of_saved_strategy(
        self,
        user_id: UUID,
        wdk_strategy_id: int,
        *,
        exclude_conversation_id: UUID | None = None,
    ) -> list[Conversation]:
        """Return conversations that import the given saved WDK strategy. A
        strategy with consumers cannot be hard-deleted."""
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.application_id == calling_application(),
            Conversation.imported_saved_strategy_ids.contains([wdk_strategy_id]),
        )
        if exclude_conversation_id is not None:
            stmt = stmt.where(Conversation.id != exclude_conversation_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_conversation(
        self, conversation_id: UUID, upd: ConversationUpdate
    ) -> None:
        """Update chat metadata from the fields present in the payload."""
        values = _collect_chat_values(upd)
        if upd.name is not None:
            conversation = await self.get_by_id(conversation_id)
            if conversation:
                upd.name = await self._deduplicate_name(
                    conversation.user_id,
                    conversation.site_id,
                    upd.name,
                    exclude_conversation_id=conversation_id,
                )
            values["name"] = upd.name

        if not values:
            return

        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(**values)
        )
        await self.session.flush()

    async def dismiss(self, conversation_id: UUID) -> None:
        """Mark a chat as dismissed, which hides it from the main list."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(dismissed_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def restore(self, conversation_id: UUID) -> None:
        """Restore a dismissed chat and clear its strategy AST."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(dismissed_at=None, strategy_ast={})
        )
        await self.session.flush()

    async def prune_wdk_orphans(
        self,
        user_id: UUID,
        site_id: str,
        live_wdk_ids: set[int],
    ) -> int:
        """Delete chats whose WDK strategy id is not in the live set and
        return how many are deleted."""
        stmt = select(Conversation.id, Conversation.wdk_strategy_id).where(
            Conversation.user_id == user_id,
            Conversation.application_id == calling_application(),
            Conversation.site_id == site_id,
            Conversation.wdk_strategy_id.is_not(None),
            Conversation.dismissed_at.is_(None),
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        orphan_ids = [
            conversation_id
            for conversation_id, wdk_id in rows
            if wdk_id not in live_wdk_ids
        ]

        if not orphan_ids:
            return 0

        await self.session.execute(
            delete(Conversation).where(Conversation.id.in_(orphan_ids))
        )
        await self.session.flush()
        return len(orphan_ids)
