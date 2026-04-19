"""Rename chats → conversations; drop and recreate cleanly.

Revision ID: 2026_04_17_0001
Revises: 2026_04_15_0001
Create Date: 2026-04-17
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from pathfinder.persistence.models import GUID

revision: str = "2026_04_17_0001"
down_revision: str | Sequence[str] | None = "2026_04_15_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoints CASCADE")

    op.execute("DROP TABLE IF EXISTS store CASCADE")
    op.execute("DROP TABLE IF EXISTS store_migrations CASCADE")
    op.execute("DROP TABLE IF EXISTS store_vectors CASCADE")
    op.execute("DROP TABLE IF EXISTS vector_migrations CASCADE")

    op.execute("DROP TABLE IF EXISTS checkpoint_labels CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_events CASCADE")
    op.execute("DROP TABLE IF EXISTS task_progress CASCADE")
    op.execute("DROP TABLE IF EXISTS background_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_tombstones CASCADE")
    op.execute("DROP TABLE IF EXISTS messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chats CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")

    op.create_table(
        "conversations",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("site_id", sa.String(50), nullable=False, server_default=""),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("record_type", sa.String(100), nullable=True),
        sa.Column("wdk_strategy_id", sa.Integer, nullable=True),
        sa.Column(
            "is_saved",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("pipeline", JSONB, nullable=True),
        sa.Column(
            "step_count", sa.Integer, nullable=False, server_default="0",
        ),
        sa.Column("plan", JSONB, nullable=False, server_default="{}"),
        sa.Column("estimated_size", sa.Integer, nullable=True),
        sa.Column(
            "gene_set_id",
            sa.String(50),
            sa.ForeignKey("gene_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "gene_set_auto_imported",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "experiment_id",
            sa.String(50),
            sa.ForeignKey("experiments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversations_user_site", "conversations", ["user_id", "site_id"],
    )
    op.create_index(
        "ix_conversations_wdk_strategy_id",
        "conversations",
        ["wdk_strategy_id"],
        unique=True,
        postgresql_where=sa.text("wdk_strategy_id IS NOT NULL"),
    )

    op.create_table(
        "messages",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("parts", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_messages_role",
        ),
    )
    op.create_index(
        "messages_conversation_id_created_at_idx",
        "messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "background_tasks",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("args", JSONB, nullable=False, server_default="{}"),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "estimated_duration_seconds",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "bg_tasks_conversation_idx",
        "background_tasks",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "task_progress",
        sa.Column(
            "id", sa.BigInteger, primary_key=True, autoincrement=True,
        ),
        sa.Column(
            "task_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("background_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("percent", sa.Float, nullable=False),
        sa.Column("message", sa.Text, nullable=False, server_default=""),
        sa.Column("data", JSONB, nullable=True),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "task_progress_task_idx", "task_progress", ["task_id", "emitted_at"],
    )

    op.create_table(
        "conversation_events",
        sa.Column(
            "id", sa.Integer, primary_key=True, autoincrement=True,
        ),
        sa.Column(
            "conversation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("background_tasks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("chunk", JSONB, nullable=False),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "conversation_events_conversation_id_idx",
        "conversation_events",
        ["conversation_id"],
    )
    op.create_index(
        "conversation_events_task_id_idx",
        "conversation_events",
        ["task_id"],
    )

    op.create_table(
        "checkpoint_labels",
        sa.Column("thread_id", sa.Text, nullable=False),
        sa.Column("checkpoint_id", sa.Text, nullable=False),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column(
            "pinned",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_id", "user_id"),
    )
    op.create_index(
        "checkpoint_labels_thread_idx", "checkpoint_labels", ["thread_id"],
    )

    op.create_table(
        "memory_tombstones",
        sa.Column(
            "id", sa.Integer, primary_key=True, autoincrement=True,
        ),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "reason",
            sa.String(32),
            nullable=False,
            server_default="user_deleted",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "content_hash",
            name="uq_tombstones_user_kind_hash",
        ),
    )
    op.create_index(
        "ix_memory_tombstones_user_id",
        "memory_tombstones",
        ["user_id"],
    )


def downgrade() -> None:
    msg = "No backwards compat — this migration is one-way."
    raise NotImplementedError(msg)
