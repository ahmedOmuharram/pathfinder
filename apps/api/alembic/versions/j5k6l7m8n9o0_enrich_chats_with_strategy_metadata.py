"""enrich chats with strategy metadata

Folds the dropped ``stream_projections`` columns into ``chats`` so the chat
identity row carries its own sidebar/strategy metadata. Part of Task 7 of the
chat/SSE overhaul: the legacy ``streams``/``stream_projections`` tables were
dropped by ``i4j5k6l7m8n9``, so the strategy routers (which still own sidebar
listings, WDK sync, dismiss/restore) must read/write this metadata directly
on ``chats``.

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-04-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j5k6l7m8n9o0"
down_revision: str | Sequence[str] | None = "i4j5k6l7m8n9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("chats", sa.Column("site_id", sa.String(50), server_default=""))
    op.add_column("chats", sa.Column("name", sa.String(255), server_default=""))
    op.add_column("chats", sa.Column("record_type", sa.String(100), nullable=True))
    op.add_column("chats", sa.Column("wdk_strategy_id", sa.Integer, nullable=True))
    op.add_column(
        "chats", sa.Column("is_saved", sa.Boolean, server_default="false")
    )
    op.add_column("chats", sa.Column("pipeline", sa.JSON, nullable=True))
    op.add_column("chats", sa.Column("step_count", sa.Integer, server_default="0"))
    op.add_column("chats", sa.Column("plan", sa.JSON, server_default="{}"))
    op.add_column("chats", sa.Column("estimated_size", sa.Integer, nullable=True))
    op.add_column(
        "chats",
        sa.Column(
            "gene_set_id",
            sa.String(50),
            sa.ForeignKey("gene_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "chats",
        sa.Column(
            "gene_set_auto_imported", sa.Boolean, server_default="false"
        ),
    )
    op.add_column(
        "chats", sa.Column("conversation_state", sa.JSON, server_default="{}")
    )
    op.add_column(
        "chats",
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "chats",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "chats",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_chats_user_site", "chats", ["user_id", "site_id"])
    op.create_index(
        "ix_chats_wdk_strategy_id",
        "chats",
        ["wdk_strategy_id"],
        unique=True,
        postgresql_where=sa.text("wdk_strategy_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_chats_wdk_strategy_id", table_name="chats")
    op.drop_index("ix_chats_user_site", table_name="chats")
    op.drop_column("chats", "updated_at")
    op.drop_column("chats", "created_at")
    op.drop_column("chats", "dismissed_at")
    op.drop_column("chats", "conversation_state")
    op.drop_column("chats", "gene_set_auto_imported")
    op.drop_column("chats", "gene_set_id")
    op.drop_column("chats", "estimated_size")
    op.drop_column("chats", "plan")
    op.drop_column("chats", "step_count")
    op.drop_column("chats", "pipeline")
    op.drop_column("chats", "is_saved")
    op.drop_column("chats", "wdk_strategy_id")
    op.drop_column("chats", "record_type")
    op.drop_column("chats", "name")
    op.drop_column("chats", "site_id")
    op.drop_column("chats", "user_id")
