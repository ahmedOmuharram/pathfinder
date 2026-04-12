"""add strategy_plans table

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-04-09 00:00:00.000000

Persist interactive strategy plans separately from stream_projections so plan
approval and execution lifecycle updates survive projection merges and can be
restored authoritatively across turns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_plans",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("stream_id", sa.CHAR(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_strategy_plans_stream_id"),
        "strategy_plans",
        ["stream_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_strategy_plans_stream_id"), table_name="strategy_plans")
    op.drop_table("strategy_plans")
