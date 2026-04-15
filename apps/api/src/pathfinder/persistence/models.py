"""SQLAlchemy ORM models."""

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine

from pathfinder.platform.types import JSONArray, JSONObject


class GUID(TypeDecorator[UUID]):
    """Platform-independent GUID type.

    Uses CHAR(36) and stores UUIDs as strings.
    Returns proper ``UUID`` objects on read so that Python-side comparisons
    (e.g. ``chat.user_id == some_uuid``) work correctly.
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

    chats: Mapped[list[Chat]] = relationship(
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


class Chat(Base):
    """A chat conversation — identity + sidebar/strategy metadata.

    Replaces the legacy ``streams`` + ``stream_projections`` pair (dropped by
    migration ``i4j5k6l7m8n9``). One row per conversation; metadata lives
    directly on this table for fast sidebar listing and WDK sync.
    ``Message`` rows carry the parts-based history (see below).
    """

    __tablename__ = "chats"
    __table_args__ = (
        Index("ix_chats_user_site", "user_id", "site_id"),
        Index(
            "ix_chats_wdk_strategy_id",
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
    pipeline: Mapped[JSONObject | None] = mapped_column(JSON, nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[JSONObject] = mapped_column(JSON, default=dict)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="chats")


class Message(Base):
    """A single turn's parts-based message row.

    One row per AI-SDK v6 ``UIMessage`` — stores all parts (text, tool calls,
    reasoning, data chunks, etc.) as a JSONB array. ``metadata`` carries
    phase/model/usage/trace-id fields outside the parts list.
    """

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_messages_role",
        ),
        Index("messages_chat_id_created_at_idx", "chat_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    chat_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    parts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
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
    chat_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
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


class ChatEvent(Base):
    """Durable chat stream chunk — enables resume/catchup after reconnect."""

    __tablename__ = "chat_events"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    chat_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chunk: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
