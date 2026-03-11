"""add dismissed_at to stream_projections

Revision ID: b4e2f3a5d6c7
Revises: a3f1b2c4d5e6
Create Date: 2026-03-11 00:00:00.000000

Adds dismissed_at column for soft-delete of WDK-linked strategies.
When set, the strategy is hidden from the main list and skipped during WDK sync.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4e2f3a5d6c7"
down_revision: str | Sequence[str] | None = "a3f1b2c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_projections",
        sa.Column(
            "dismissed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("stream_projections", "dismissed_at")
