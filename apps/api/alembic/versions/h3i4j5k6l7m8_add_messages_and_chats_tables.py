"""add parts-based messages + chats tables (additive)

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-04-13 00:00:00.000000

Task 3 of the chat/SSE overhaul. Introduces the new ``chats`` + ``messages``
schema that replaces the legacy ``streams`` / ``stream_projections`` /
``chat_messages``-style tables. The old tables remain in service while Tasks
4-6 wire up the new pipeline dispatcher + frontend; Task 7 drops them.

``messages.parts`` stores AI-SDK v6 ``UIMessagePart[]`` as JSONB;
``messages.metadata`` holds phase/model/usage/trace-id fields.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "h3i4j5k6l7m8"
down_revision: str | Sequence[str] | None = "g2h3i4j5k6l7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the new ``chats`` and ``messages`` tables."""
    op.create_table(
        "chats",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "chat_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("parts", JSONB, nullable=False),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_messages_role",
        ),
    )
    op.create_index(
        "messages_chat_id_created_at_idx",
        "messages",
        ["chat_id", "created_at"],
    )


def downgrade() -> None:
    """Drop the new ``messages`` and ``chats`` tables (messages first for FK)."""
    op.drop_index("messages_chat_id_created_at_idx", table_name="messages")
    op.drop_table("messages")
    op.drop_table("chats")
