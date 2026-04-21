"""Add scratchpad_notes and scratchpad_compactions tables.

Scratchpad is conversation-scoped working memory for phase agents: each
note has a title, summary, and markdown body; a GENERATED ALWAYS tsvector
column powers FTS for search_notes(); tags are JSONB for flexible tagging
without a join table. The scratchpad_compactions table is the audit log
for LLM-driven compaction runs triggered on verification done.

Revision ID: 2026_04_20_0001
Revises: 2026_04_18_0006
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "2026_04_20_0001"
down_revision: str | Sequence[str] | None = "2026_04_18_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scratchpad_notes",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("body_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "fts",
            TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') "
                "|| setweight(to_tsvector('english', coalesce(summary, '')), 'B') "
                "|| setweight(to_tsvector('english', coalesce(body, '')), 'C')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "scratchpad_notes_conv_idx",
        "scratchpad_notes",
        ["conversation_id", sa.text("pinned DESC"), sa.text("created_at DESC")],
    )
    op.create_index(
        "scratchpad_notes_fts_idx",
        "scratchpad_notes",
        ["fts"],
        postgresql_using="gin",
    )
    op.create_index(
        "scratchpad_notes_tags_idx",
        "scratchpad_notes",
        ["tags"],
        postgresql_using="gin",
        postgresql_ops={"tags": "jsonb_path_ops"},
    )

    op.create_table(
        "scratchpad_compactions",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            primary_key=True,
        ),
        sa.Column(
            "conversation_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("before_count", sa.Integer(), nullable=False),
        sa.Column("after_count", sa.Integer(), nullable=False),
        sa.Column("before_tokens", sa.Integer(), nullable=False),
        sa.Column("after_tokens", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("trigger_reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "trigger_reason IN ('count', 'tokens', 'both')",
            name="ck_scratchpad_compactions_trigger_reason",
        ),
    )
    op.create_index(
        "scratchpad_compactions_conv_idx",
        "scratchpad_compactions",
        ["conversation_id", sa.text("triggered_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "scratchpad_compactions_conv_idx", table_name="scratchpad_compactions"
    )
    op.drop_table("scratchpad_compactions")
    op.drop_index("scratchpad_notes_tags_idx", table_name="scratchpad_notes")
    op.drop_index("scratchpad_notes_fts_idx", table_name="scratchpad_notes")
    op.drop_index("scratchpad_notes_conv_idx", table_name="scratchpad_notes")
    op.drop_table("scratchpad_notes")
