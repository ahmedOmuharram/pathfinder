"""Give a thread's strategy a revision history.

Fork and revert read the strategy as it stood at a chosen message. Without a
per-revision snapshot both operations can only copy the latest AST.

Revision ID: 2026_08_30_0003
Revises: 2026_08_30_0002
Create Date: 2026-08-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_08_30_0003"
down_revision: str | Sequence[str] | None = "2026_08_30_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_revisions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("record_type", sa.String(length=100), nullable=True),
        sa.Column(
            "strategy_ast",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wdk_strategy_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_strategy_revisions_conversation_created",
        "strategy_revisions",
        ["conversation_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_revisions_conversation_created",
        table_name="strategy_revisions",
    )
    op.drop_table("strategy_revisions")
