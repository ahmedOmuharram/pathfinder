"""add_eval_data_consent_and_staging

Revision ID: 2026_08_23_0001
Revises: 2026_08_22_0001
Create Date: 2026-08-23 00:00:00.000000

Eval-data consent on the user, and the staging queue extraction writes into.
The consent column is additive and defaults on, which is the ruled default.
The staging table's check constraint is the linkage rule: a staged row names
its user and thread, a promoted row names neither and holds no extract.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_08_23_0001"
down_revision: str | Sequence[str] | None = "2026_08_22_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINKAGE_ENDS_AT_PROMOTION = (
    "(status = 'staged'"
    " AND user_id IS NOT NULL"
    " AND source_conversation_id IS NOT NULL"
    " AND extract IS NOT NULL)"
    " OR "
    "(status = 'promoted'"
    " AND user_id IS NULL"
    " AND source_conversation_id IS NULL"
    " AND extract IS NULL)"
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "eval_data_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("eval_notice_seen_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "eval_staged_cases",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("user_id", sa.CHAR(length=36), nullable=True),
        sa.Column(
            "source_conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "application_id",
            sa.String(length=64),
            nullable=False,
            server_default="pathfinder",
        ),
        sa.Column("site_id", sa.String(length=50), nullable=False),
        sa.Column("assistant_id", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("extract", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="staged",
        ),
        sa.Column("corpus_name", sa.String(length=128), nullable=True),
        sa.Column(
            "staged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('staged', 'promoted')",
            name="ck_eval_staged_cases_status",
        ),
        sa.CheckConstraint(
            _LINKAGE_ENDS_AT_PROMOTION,
            name="ck_eval_staged_cases_linkage_ends_at_promotion",
        ),
        sa.UniqueConstraint("content_hash", name="uq_eval_staged_cases_content_hash"),
    )
    op.create_index(
        "ix_eval_staged_cases_source_conversation",
        "eval_staged_cases",
        ["source_conversation_id"],
        unique=True,
        postgresql_where=sa.text("source_conversation_id IS NOT NULL"),
    )
    op.create_index(
        "ix_eval_staged_cases_user_id",
        "eval_staged_cases",
        ["user_id"],
    )
    op.create_index(
        "ix_eval_staged_cases_status",
        "eval_staged_cases",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_eval_staged_cases_status", table_name="eval_staged_cases")
    op.drop_index("ix_eval_staged_cases_user_id", table_name="eval_staged_cases")
    op.drop_index(
        "ix_eval_staged_cases_source_conversation",
        table_name="eval_staged_cases",
    )
    op.drop_table("eval_staged_cases")
    op.drop_column("users", "eval_notice_seen_at")
    op.drop_column("users", "eval_data_consent")
