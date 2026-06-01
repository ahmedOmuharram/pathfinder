"""add_exports_table

Revision ID: 5fc62ca94b51
Revises: c832cac9ff78
Create Date: 2026-04-14 12:18:35.494732

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5fc62ca94b51"
down_revision: str | Sequence[str] | None = "c832cac9ff78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_exports_expires_at", "exports", ["expires_at"])
    op.create_index("ix_exports_user_id", "exports", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_exports_user_id", table_name="exports")
    op.drop_index("ix_exports_expires_at", table_name="exports")
    op.drop_table("exports")
