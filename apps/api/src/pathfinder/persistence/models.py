"""SQLAlchemy ORM models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine

from pathfinder.platform.types import JSONArray, JSONObject


class GUID(TypeDecorator[UUID]):
    """Platform-independent GUID type.

    Uses CHAR(36) and stores UUIDs as strings.
    Returns proper ``UUID`` objects on read so that Python-side comparisons
    (e.g. ``conversation.user_id == some_uuid``) work correctly.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[str]:
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
        self, value: UUID | str | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        return value

    def process_result_value(
        self, value: str | UUID | None, dialect: Dialect
    ) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(value)


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map: ClassVar[dict[type, type]] = {
        dict: JSON,
        list: JSON,
        UUID: GUID,
    }


class User(Base):
    """User model for tracking strategies."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    monthly_cost_limit_usd: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    monthly_usage: Mapped[list["MonthlyUsage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ControlSet(Base):
    """Reusable control gene set with provenance metadata."""

    __tablename__ = "control_sets"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    site_id: Mapped[str] = mapped_column(String(100))
    record_type: Mapped[str] = mapped_column(String(100))
    positive_ids: Mapped[JSONArray] = mapped_column(JSON, default=list)
    negative_ids: Mapped[JSONArray] = mapped_column(JSON, default=list)
    source: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[JSONArray] = mapped_column(JSON, default=list)
    provenance_notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_control_sets_site_id", "site_id"),
        Index("ix_control_sets_user_id", "user_id"),
    )


class ExperimentRow(Base):
    """Persisted experiment with full JSON blob."""

    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    site_id: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    data: Mapped[JSONObject] = mapped_column(JSON, default=dict)
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    benchmark_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_experiments_site_id", "site_id"),
        Index("ix_experiments_user_id", "user_id"),
        Index("ix_experiments_batch_id", "batch_id"),
        Index("ix_experiments_benchmark_id", "benchmark_id"),
    )


class GeneSetRow(Base):
    """Persisted gene set for workbench analysis."""

    __tablename__ = "gene_sets"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    site_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255), default="")
    gene_ids: Mapped[JSONArray] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="paste")
    wdk_strategy_id: Mapped[int | None] = mapped_column(nullable=True)
    wdk_step_id: Mapped[int | None] = mapped_column(nullable=True)
    search_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parameters: Mapped[JSONObject | None] = mapped_column(JSON, nullable=True)
    parent_set_ids: Mapped[JSONArray] = mapped_column(JSON, default=list)
    operation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_gene_sets_user_id", "user_id"),
        Index("ix_gene_sets_site_id", "site_id"),
        Index("ix_gene_sets_user_site", "user_id", "site_id"),
    )


class Conversation(Base):
    """A conversation — message thread + built strategy AST + WDK linkage on one row."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_site", "user_id", "site_id"),
        Index(
            "ix_conversations_wdk_strategy_id",
            "wdk_strategy_id",
            unique=True,
            postgresql_where="wdk_strategy_id IS NOT NULL",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE")
    )
    site_id: Mapped[str] = mapped_column(String(50), default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wdk_strategy_id: Mapped[int | None] = mapped_column(nullable=True)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    strategy_ast: Mapped[JSONObject] = mapped_column(JSON, default=dict)
    estimated_size: Mapped[int | None] = mapped_column(nullable=True)
    gene_set_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("gene_sets.id", ondelete="SET NULL"), nullable=True
    )
    gene_set_auto_imported: Mapped[bool] = mapped_column(Boolean, default=False)
    experiment_id: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    parent_conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    # WDK strategy ids of saved sub-strategies referenced by this conversation
    # (via expanded combiner inputs). Used as a deletion guard: a saved
    # strategy with at least one consumer cannot be deleted.
    imported_saved_strategy_ids: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="conversations")


class Message(Base):
    """Per-turn metadata row — the chunk log in ``conversation_events`` is the
    canonical source for ``parts``. Kept for usage accounting + trace ids."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_messages_role",
        ),
        Index(
            "messages_conversation_id_created_at_idx",
            "conversation_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    # Python attribute name uses a trailing underscore because ``metadata`` is
    # reserved on SQLAlchemy's ``DeclarativeBase``. The underlying column name
    # is still ``metadata``.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Export(Base):
    """Temporary download artifact with TTL."""

    __tablename__ = "exports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class MemoryTombstoneRow(Base):
    """Soft-delete marker that prevents auto-write from re-adding pruned memories."""

    __tablename__ = "memory_tombstones"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user_deleted"
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "kind",
            "content_hash",
            name="uq_tombstones_user_kind_hash",
        ),
    )


class BackgroundTask(Base):
    """Durable task row for long-running agent tools dispatched to the worker."""

    __tablename__ = "background_tasks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    args: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TaskProgress(Base):
    """Incremental progress record emitted by a background task."""

    __tablename__ = "task_progress"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ConversationEvent(Base):
    """Durable conversation stream chunk — enables resume/catchup after reconnect."""

    __tablename__ = "conversation_events"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    turn_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    chunk: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ChatTurnCancellation(Base):
    __tablename__ = "chat_turn_cancellations"

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    turn_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ScratchpadNote(Base):
    """Agent-written working-memory note, conversation-scoped."""

    __tablename__ = "scratchpad_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]",
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    body_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    fts: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') "
            "|| setweight(to_tsvector('english', coalesce(summary, '')), 'B') "
            "|| setweight(to_tsvector('english', coalesce(body, '')), 'C')",
            persisted=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ScratchpadCompaction(Base):
    """Audit row for one scratchpad compaction run."""

    __tablename__ = "scratchpad_compactions"
    __table_args__ = (
        CheckConstraint(
            "trigger_reason IN ('count', 'tokens', 'both')",
            name="ck_scratchpad_compactions_trigger_reason",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), primary_key=True
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    before_count: Mapped[int] = mapped_column(Integer, nullable=False)
    after_count: Mapped[int] = mapped_column(Integer, nullable=False)
    before_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    after_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=6), nullable=False, server_default="0",
    )
    trigger_reason: Mapped[str] = mapped_column(String, nullable=False)


class MonthlyUsage(Base):
    """Per-user, per-month accumulated token + cost usage.

    ``period_start`` is always the first-of-month UTC date; the quota
    rolls over when a new month begins. Accumulation is an UPSERT keyed on
    ``(user_id, period_start)``.
    """

    __tablename__ = "monthly_usage"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, server_default=text("0")
    )
    total_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="monthly_usage")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "period_start", name="monthly_usage_user_period_key"
        ),
        Index("monthly_usage_user_idx", "user_id"),
    )
