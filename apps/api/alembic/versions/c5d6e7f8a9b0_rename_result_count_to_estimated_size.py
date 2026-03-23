"""rename result_count to estimated_size

Revision ID: c5d6e7f8a9b0
Revises: b4e2f3a5d6c7
Create Date: 2026-03-23 00:00:00.000000

WDK uses estimatedSize on Step responses. Align our column name.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | Sequence[str] | None = "b4e2f3a5d6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "stream_projections", "result_count", new_column_name="estimated_size"
    )


def downgrade() -> None:
    op.alter_column(
        "stream_projections", "estimated_size", new_column_name="result_count"
    )
