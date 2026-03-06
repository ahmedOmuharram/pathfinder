"""SQLAlchemy ORM models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine

from veupath_chatbot.platform.types import JSONArray, JSONObject


class GUID(TypeDecorator[UUID]):
    """Platform-independent GUID type.

    Uses CHAR(36) and stores UUIDs as strings.
    Returns proper ``UUID`` objects on read so that Python-side comparisons
    (e.g. ``stream.user_id == some_uuid``) work correctly.
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

    type_annotation_map = {
        JSONObject: JSON,
        JSONArray: JSON,
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

    # Relationships
    streams: Mapped[list[Stream]] = relationship(
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
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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


class Stream(Base):
    """A conversation stream — the identity of a chat conversation.

    All mutable state is derived from events in Redis. This table only
    holds identity and ownership.
    """

    __tablename__ = "streams"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE")
    )
    site_id: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="streams")

    __table_args__ = (Index("ix_streams_user_site", "user_id", "site_id"),)


class StreamProjection(Base):
    """Materialized projection of a conversation stream.

    Derived from events — rebuildable by replaying the Redis stream.
    This is a CACHE for fast reads, not a source of truth.
    """

    __tablename__ = "stream_projections"

    stream_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("streams.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), default="")
    record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wdk_strategy_id: Mapped[int | None] = mapped_column(nullable=True)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[JSONObject] = mapped_column(JSON, default=dict)
    steps: Mapped[JSONArray] = mapped_column(JSON, default=list)
    root_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_count: Mapped[int | None] = mapped_column(nullable=True)
    last_event_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    site_id: Mapped[str] = mapped_column(String(50), default="")

    stream: Mapped[Stream] = relationship()

    __table_args__ = (
        Index(
            "ix_proj_wdk",
            "wdk_strategy_id",
            unique=True,
            postgresql_where="wdk_strategy_id IS NOT NULL",
        ),
    )


class GeneSetRow(Base):
    """Persisted gene set for workbench analysis."""

    __tablename__ = "gene_sets"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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


class Operation(Base):
    """Tracks active and completed operations for client discovery."""

    __tablename__ = "operations"

    operation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    stream_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("streams.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    stream: Mapped[Stream] = relationship()

    __table_args__ = (Index("ix_ops_stream_status", "stream_id", "status"),)
