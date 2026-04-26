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
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import Conversation


@dataclass
class ConversationUpdate:
    """Partial update payload for a ``Conversation``.

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
    strategy_ast: StrategyAst | None = None
    step_count: int | None = None
    estimated_size: int | None = None
    estimated_size_set: bool = False
    gene_set_id: str | None = None
    gene_set_id_set: bool = False
    gene_set_auto_imported: bool | None = None
    pipeline: Any | None = field(default=None)
    supervisor_model_id: str | None = None
    supervisor_model_id_set: bool = False
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
    ("supervisor_model_id_set", "supervisor_model_id"),
)


def _collect_chat_values(upd: ConversationUpdate) -> dict[str, Any]:
    """Build the SQL column-value dict from non-None / flagged fields."""
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

    for flag, attr in _FLAGGED_FIELDS:
        if getattr(upd, flag):
            values[attr] = getattr(upd, attr)

    return values


class ConversationRepository:
    """Data access for chat conversations (identity + strategy metadata)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Helpers ──

    async def _deduplicate_name(
        self,
        user_id: UUID,
        site_id: str,
        name: str,
        exclude_conversation_id: UUID | None = None,
    ) -> str:
        """Return a unique name for a chat within (user, site).

        If ``name`` already exists, appends ``(1)``, ``(2)``, etc.
        """
        query = (
            select(Conversation.name)
            .where(Conversation.user_id == user_id, Conversation.site_id == site_id)
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

    # ── Identity ──

    async def create(
        self,
        user_id: UUID,
        site_id: str,
        *,
        conversation_id: UUID | None = None,
        name: str = "",
    ) -> Conversation:
        """Create a new chat with a deduplicated name.

        The keyword ``conversation_id`` lets callers supply a pre-generated UUID so
        the same id travels through ``useChat({ id })`` on the frontend.
        """
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
        result = await self.session.execute(select(Conversation).where(Conversation.id == conversation_id))
        return result.scalar_one_or_none()

    async def get_by_id_with_strategy_lock(
        self, conversation_id: UUID
    ) -> Conversation | None:
        # Postgres advisory xact lock keyed on the strategy id. Auto-released
        # at transaction end (same lifecycle as SELECT FOR UPDATE) but doesn't
        # block concurrent reads of the same row.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"strategy:{conversation_id}"},
        )
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def delete(
        self, conversation_id: UUID, *, cascade: bool = False,
    ) -> None:
        """Delete a conversation.

        Two modes:
        * ``cascade=False`` (default): delete only this node; promote its
          direct children to this node's parent, inheriting the fork point
          so the remaining tree stays meaningful.
        * ``cascade=True``: delete this node and every descendant. Uses a
          recursive CTE to find the full subtree in one query.
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

    # ── Strategy metadata reads ──

    async def list_conversations(
        self,
        user_id: UUID,
        site_id: str | None = None,
        limit: int = 50,
    ) -> list[Conversation]:
        """List active (non-dismissed) chats, newest-updated first."""
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
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
                Conversation.wdk_strategy_id == wdk_strategy_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Strategy metadata writes ──

    async def update_conversation(self, conversation_id: UUID, upd: ConversationUpdate) -> None:
        """Dynamically update chat metadata based on provided fields."""
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
            update(Conversation).where(Conversation.id == conversation_id).values(**values)
        )
        await self.session.flush()

    async def commit_partial(self) -> None:
        """Commit the underlying session immediately.

        Used by `apply_step_patch` to make partial-success WDK push state
        durable before raising `PartialPushError`. Without this the
        request-session middleware would roll back on the raised exception
        and the next user retry would see no progress (and re-create the
        already-pushed steps in WDK).
        """
        await self.session.commit()

    async def dismiss(self, conversation_id: UUID) -> None:
        """Soft-delete: mark a chat as dismissed (hidden from main list)."""
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(dismissed_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def restore(self, conversation_id: UUID) -> None:
        """Un-dismiss a chat and reset strategy AST for fresh WDK import."""
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
        """Delete chats whose ``wdk_strategy_id`` is not in the live set.

        Returns the number of pruned chats.
        """
        stmt = (
            select(Conversation.id, Conversation.wdk_strategy_id)
            .where(
                Conversation.user_id == user_id,
                Conversation.site_id == site_id,
                Conversation.wdk_strategy_id.is_not(None),
                Conversation.dismissed_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        orphan_ids = [
            conversation_id for conversation_id, wdk_id in rows if wdk_id not in live_wdk_ids
        ]

        if not orphan_ids:
            return 0

        await self.session.execute(delete(Conversation).where(Conversation.id.in_(orphan_ids)))
        await self.session.flush()
        return len(orphan_ids)
