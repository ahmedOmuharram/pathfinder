"""add chat_turn_cancellations table

Revision ID: 2026_05_04_0001
Revises: f1b8d4a92c70
Create Date: 2026-05-04 09:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "2026_05_04_0001"
down_revision: str | Sequence[str] | None = "f1b8d4a92c70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_turn_cancellations",
        sa.Column("conversation_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("turn_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id", "turn_id", name="pk_chat_turn_cancellations",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("chat_turn_cancellations")
