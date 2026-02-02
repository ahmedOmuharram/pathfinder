"""SQLAlchemy ORM models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, CHAR


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    
    Uses CHAR(36) for SQLite compatibility, stores as string.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, UUID):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, UUID):
            return UUID(value)
        return value


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map = {
        dict[str, Any]: JSON,
        list[dict[str, Any]]: JSON,
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
    strategies: Mapped[list["Strategy"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Strategy(Base):
    """Saved strategy with full state."""

    __tablename__ = "strategies"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    site_id: Mapped[str] = mapped_column(String(50))
    record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255))

    # Strategy plan as JSON (DSL AST)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Compiled steps
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    root_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # WDK strategy ID (if pushed to VEuPathDB)
    wdk_strategy_id: Mapped[int | None] = mapped_column()

    # Result counts
    result_count: Mapped[int | None] = mapped_column()
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    thinking: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="strategies")

    __table_args__ = (
        Index("ix_strategies_user_id", "user_id"),
        Index("ix_strategies_site_id", "site_id"),
    )


class StrategyHistory(Base):
    """Version history for strategy edits (for undo/redo)."""

    __tablename__ = "strategy_history"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    strategy_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("strategies.id", ondelete="CASCADE"),
    )
    version: Mapped[int] = mapped_column()
    plan: Mapped[dict[str, Any]] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_strategy_history_strategy_version", "strategy_id", "version"),)
