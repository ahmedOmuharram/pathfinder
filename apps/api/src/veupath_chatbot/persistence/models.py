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


class GUID(TypeDecorator[str]):
    """Platform-independent GUID type.

    Uses CHAR(36) and stores UUIDs as strings.


    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[str]:
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
        self, value: UUID | str | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return value
        if isinstance(value, UUID):
            return str(value)
        return value

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return value
        if isinstance(value, UUID):
            return str(value)
        return value


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
    strategies: Mapped[list[Strategy]] = relationship(
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
    plan: Mapped[JSONObject] = mapped_column(JSON, default=dict)

    # Compiled steps
    steps: Mapped[JSONArray] = mapped_column(JSON, default=list)
    root_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # WDK strategy ID (if synced to VEuPathDB)
    wdk_strategy_id: Mapped[int | None] = mapped_column()

    # Draft/saved state — mirrors WDK's isSaved flag.
    # False = draft (auto-synced working state), True = user-promoted saved.
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Result counts
    result_count: Mapped[int | None] = mapped_column()
    messages: Mapped[JSONArray] = mapped_column(JSON, default=list)
    thinking: Mapped[JSONObject | None] = mapped_column(JSON, default=None)

    # Persisted model selection (catalog ID, e.g. "openai/gpt-5").
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="strategies")

    __table_args__ = (
        Index("ix_strategies_user_id", "user_id"),
        Index("ix_strategies_site_id", "site_id"),
        Index(
            "ix_strategies_user_wdk",
            "user_id",
            "wdk_strategy_id",
            unique=True,
            postgresql_where="wdk_strategy_id IS NOT NULL",
        ),
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
    plan: Mapped[JSONObject] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_strategy_history_strategy_version", "strategy_id", "version"),
    )


class PlanSession(Base):
    """Planning workspace session (not tied to a strategy graph)."""

    __tablename__ = "plan_sessions"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE")
    )
    site_id: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255), default="New Conversation")

    # Conversation + planner outputs
    messages: Mapped[JSONArray] = mapped_column(JSON, default=list)
    thinking: Mapped[JSONObject | None] = mapped_column(JSON, default=None)
    planning_artifacts: Mapped[JSONArray] = mapped_column(JSON, default=list)

    # Persisted model selection (catalog ID, e.g. "openai/gpt-5").
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_plan_sessions_user_id", "user_id"),
        Index("ix_plan_sessions_site_id", "site_id"),
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
    name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    data: Mapped[JSONObject] = mapped_column(JSON, default=dict)
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    benchmark_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_experiments_site_id", "site_id"),
        Index("ix_experiments_batch_id", "batch_id"),
        Index("ix_experiments_benchmark_id", "benchmark_id"),
    )
