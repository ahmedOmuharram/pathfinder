"""add_memory_tombstones

Revision ID: 29b8e0c301b3
Revises: 5fc62ca94b51
Create Date: 2026-04-14 12:49:13.185516

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "29b8e0c301b3"
down_revision: str | Sequence[str] | None = "5fc62ca94b51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "memory_tombstones",
        sa.Column(
            "id",
            sa.Integer,
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(36),
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
            server_default=sa.func.now(),
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
    """Downgrade schema."""
    op.drop_index("ix_memory_tombstones_user_id", table_name="memory_tombstones")
    op.drop_table("memory_tombstones")
