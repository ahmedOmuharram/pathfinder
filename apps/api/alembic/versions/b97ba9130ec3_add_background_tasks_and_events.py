"""add_background_tasks_and_events

Revision ID: b97ba9130ec3
Revises: 3efc8ac5248a
Create Date: 2026-04-14 13:57:14.195849

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

# revision identifiers, used by Alembic.
revision: str = "b97ba9130ec3"
down_revision: str | Sequence[str] | None = "3efc8ac5248a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create background_tasks, task_progress, and chat_events."""
    op.create_table(
        "background_tasks",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("args", JSONB, nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "estimated_duration_seconds",
            sa.Integer,
            nullable=False,
            server_default="60",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_background_tasks_chat_id", "background_tasks", ["chat_id"])
    op.create_index("ix_background_tasks_user_id", "background_tasks", ["user_id"])

    op.create_table(
        "task_progress",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "task_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("background_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("percent", sa.Float, nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.Column(
            "emitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_task_progress_task_id", "task_progress", ["task_id"])

    op.create_table(
        "chat_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "chat_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
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
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_events_chat_id", "chat_events", ["chat_id"])
    op.create_index("ix_chat_events_task_id", "chat_events", ["task_id"])


def downgrade() -> None:
    """Drop chat_events, task_progress, and background_tasks."""
    op.drop_index("ix_chat_events_task_id", table_name="chat_events")
    op.drop_index("ix_chat_events_chat_id", table_name="chat_events")
    op.drop_table("chat_events")
    op.drop_index("ix_task_progress_task_id", table_name="task_progress")
    op.drop_table("task_progress")
    op.drop_index("ix_background_tasks_user_id", table_name="background_tasks")
    op.drop_index("ix_background_tasks_chat_id", table_name="background_tasks")
    op.drop_table("background_tasks")
