"""Attach one open EDA analysis to a chat thread.

A thread gets a row only while it holds an open EDA analysis. The upstream EDA
user service owns the document, so the row carries the reference and the
mutation counter, never the descriptor.

Revision ID: 2026_08_28_0002
Revises: 2026_08_28_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_08_28_0002"
down_revision: str | Sequence[str] | None = "2026_08_28_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_analyses",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("site_id", sa.String(50), nullable=False),
        sa.Column("dataset_id", sa.String(100), nullable=False),
        sa.Column("analysis_id", sa.String(100), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversation_analyses_dataset_id",
        "conversation_analyses",
        ["dataset_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_analyses_dataset_id",
        table_name="conversation_analyses",
    )
    op.drop_table("conversation_analyses")
