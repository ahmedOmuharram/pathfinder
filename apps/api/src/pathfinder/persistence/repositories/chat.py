"""Repository for chat (conversation) identity + sidebar/strategy metadata.

Replaces the legacy ``StreamRepository`` (streams + stream_projections + the
operations side-channel) — the ``operations`` table is gone with the chat
overhaul, so this repository exposes a single clean surface for creating
chats, updating strategy metadata, and driving the conversation sidebar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload
from pathfinder.persistence.models import Chat


@dataclass
class ChatUpdate:
    """Partial update payload for a ``Chat``.

    Only fields explicitly set to non-None (or flagged with ``*_set=True``)
    are written. Use ``wdk_strategy_id_set=True`` to explicitly set that
    field (even to ``None``), similarly for ``is_saved_set``,
    ``estimated_size_set``, ``gene_set_id_set``.
    """

    name: str | None = None
    record_type: str | None = None
    wdk_strategy_id: int | None = None
    wdk_strategy_id_set: bool = False
    is_saved: bool | None = None
    is_saved_set: bool = False
    plan: StrategyPlanPayload | None = None
    step_count: int | None = None
    estimated_size: int | None = None
    estimated_size_set: bool = False
    gene_set_id: str | None = None
    gene_set_id_set: bool = False
    gene_set_auto_imported: bool | None = None
    pipeline: Any | None = field(default=None)
    touch_updated_at: bool = True


_SIMPLE_FIELDS: tuple[str, ...] = (
    "record_type",
    "step_count",
    "gene_set_auto_imported",
    "pipeline",
)

_FLAGGED_FIELDS: tuple[tuple[str, str], ...] = (
    ("wdk_strategy_id_set", "wdk_strategy_id"),
    ("estimated_size_set", "estimated_size"),
    ("gene_set_id_set", "gene_set_id"),
    ("is_saved_set", "is_saved"),
)


def _collect_chat_values(upd: ChatUpdate) -> dict[str, Any]:
    """Build the SQL column-value dict from non-None / flagged fields."""
    values: dict[str, Any] = {}
    if upd.touch_updated_at:
        values["updated_at"] = datetime.now(UTC)

    for attr in _SIMPLE_FIELDS:
        val = getattr(upd, attr)
        if val is not None:
            values[attr] = val

    if upd.plan is not None:
        values["plan"] = upd.plan.model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )

    for flag, attr in _FLAGGED_FIELDS:
        if getattr(upd, flag):
            values[attr] = getattr(upd, attr)

    return values


class ChatRepository:
    """Data access for chat conversations (identity + strategy metadata)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Helpers ──

    async def _deduplicate_name(
        self,
        user_id: UUID,
        site_id: str,
        name: str,
        exclude_chat_id: UUID | None = None,
    ) -> str:
        """Return a unique name for a chat within (user, site).

        If ``name`` already exists, appends ``(1)``, ``(2)``, etc.
        """
        query = (
            select(Chat.name)
            .where(Chat.user_id == user_id, Chat.site_id == site_id)
        )
        if exclude_chat_id is not None:
            query = query.where(Chat.id != exclude_chat_id)
        result = await self.session.execute(query)
        existing: set[str] = {row[0] for row in result.all() if row[0]}

        if name not in existing:
            return name

        i = 1
        while f"{name} ({i})" in existing:
            i += 1
        return f"{name} ({i})"

    # ── Identity ──

    async def create(
        self,
        user_id: UUID,
        site_id: str,
        *,
        chat_id: UUID | None = None,
        name: str = "",
    ) -> Chat:
        """Create a new chat with a deduplicated name.

        The keyword ``chat_id`` lets callers supply a pre-generated UUID so
        the same id travels through ``useChat({ id })`` on the frontend.
        """
        resolved_name = await self._deduplicate_name(
            user_id,
            site_id,
            name or DEFAULT_STREAM_NAME,
        )
        chat = Chat(
            id=chat_id or uuid4(),
            user_id=user_id,
            site_id=site_id,
            name=resolved_name,
        )
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def get_by_id(self, chat_id: UUID) -> Chat | None:
        result = await self.session.execute(select(Chat).where(Chat.id == chat_id))
        return result.scalar_one_or_none()

    async def delete(self, chat_id: UUID) -> None:
        await self.session.execute(delete(Chat).where(Chat.id == chat_id))
        await self.session.flush()

    # ── Strategy metadata reads ──

    async def list_chats(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[Chat]:
        """List active (non-dismissed) chats, newest-updated first."""
        stmt = (
            select(Chat)
            .where(Chat.user_id == user_id)
            .where(Chat.dismissed_at.is_(None))
            .order_by(Chat.updated_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Chat.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list_dismissed_chats(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[Chat]:
        stmt = (
            select(Chat)
            .where(Chat.user_id == user_id)
            .where(Chat.dismissed_at.is_not(None))
            .order_by(Chat.dismissed_at.desc())
            .limit(limit)
        )
        if site_id:
            stmt = stmt.where(Chat.site_id == site_id)
        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_wdk_strategy_id(
        self, user_id: UUID, wdk_strategy_id: int
    ) -> Chat | None:
        result = await self.session.execute(
            select(Chat).where(
                Chat.user_id == user_id,
                Chat.wdk_strategy_id == wdk_strategy_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Strategy metadata writes ──

    async def update_chat(self, chat_id: UUID, upd: ChatUpdate) -> None:
        """Dynamically update chat metadata based on provided fields."""
        values = _collect_chat_values(upd)
        if upd.name is not None:
            chat = await self.get_by_id(chat_id)
            if chat:
                upd.name = await self._deduplicate_name(
                    chat.user_id,
                    chat.site_id,
                    upd.name,
                    exclude_chat_id=chat_id,
                )
            values["name"] = upd.name

        if not values:
            return

        await self.session.execute(
            update(Chat).where(Chat.id == chat_id).values(**values)
        )
        await self.session.flush()

    async def update_conversation_state(
        self, chat_id: UUID, state: dict[str, Any]
    ) -> None:
        """Replace the conversation FSM snapshot on a chat."""
        await self.session.execute(
            update(Chat)
            .where(Chat.id == chat_id)
            .values(conversation_state=state, updated_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def dismiss(self, chat_id: UUID) -> None:
        """Soft-delete: mark a chat as dismissed (hidden from main list)."""
        await self.session.execute(
            update(Chat)
            .where(Chat.id == chat_id)
            .values(dismissed_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def restore(self, chat_id: UUID) -> None:
        """Un-dismiss a chat and reset strategy scratchpad for fresh WDK import."""
        await self.session.execute(
            update(Chat)
            .where(Chat.id == chat_id)
            .values(dismissed_at=None, plan={})
        )
        await self.session.flush()

    async def prune_wdk_orphans(
        self,
        user_id: UUID,
        site_id: str,
        live_wdk_ids: set[int],
    ) -> int:
        """Delete chats whose ``wdk_strategy_id`` is not in the live set.

        Returns the number of pruned chats.
        """
        stmt = (
            select(Chat.id, Chat.wdk_strategy_id)
            .where(
                Chat.user_id == user_id,
                Chat.site_id == site_id,
                Chat.wdk_strategy_id.is_not(None),
                Chat.dismissed_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        orphan_ids = [
            chat_id for chat_id, wdk_id in rows if wdk_id not in live_wdk_ids
        ]

        if not orphan_ids:
            return 0

        await self.session.execute(delete(Chat).where(Chat.id.in_(orphan_ids)))
        await self.session.flush()
        return len(orphan_ids)
