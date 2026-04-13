"""add conversation_state column to stream_projections

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-12 00:00:00.000000

Persist the conversation FSM state (current phase, plan status, completed
phases) directly in the projection so that cross-turn resumability does not
depend on lossy Redis event scanning.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g2h3i4j5k6l7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_projections",
        sa.Column(
            "conversation_state",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("stream_projections", "conversation_state")
