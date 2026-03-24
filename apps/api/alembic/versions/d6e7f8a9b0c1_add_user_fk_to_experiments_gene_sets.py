"""add user FK to experiments and gene_sets

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-03-24 00:00:00.000000

Unify user_id column types: experiments and gene_sets used String(36) without
a foreign key, while control_sets and streams used GUID() with FK. This
migration alters the column type to CHAR(36) (matching GUID storage) and adds
FK constraints with SET NULL on delete.

Orphaned rows (user_id not in users.id) are nulled out before the FK is added.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Null out orphaned user_ids before adding FK constraints
    op.execute(
        "UPDATE experiments SET user_id = NULL "
        "WHERE user_id IS NOT NULL "
        "AND user_id NOT IN (SELECT CAST(id AS VARCHAR(36)) FROM users)"
    )
    op.execute(
        "UPDATE gene_sets SET user_id = NULL "
        "WHERE user_id IS NOT NULL "
        "AND user_id NOT IN (SELECT CAST(id AS VARCHAR(36)) FROM users)"
    )

    # Alter column type from String(36) to CHAR(36) to match GUID storage
    op.alter_column(
        "experiments",
        "user_id",
        type_=sa.CHAR(36),
        existing_type=sa.String(36),
        existing_nullable=True,
    )
    op.alter_column(
        "gene_sets",
        "user_id",
        type_=sa.CHAR(36),
        existing_type=sa.String(36),
        existing_nullable=True,
    )

    # Add foreign key constraints
    op.create_foreign_key(
        "fk_experiments_user_id",
        "experiments",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_gene_sets_user_id",
        "gene_sets",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_gene_sets_user_id", "gene_sets", type_="foreignkey")
    op.drop_constraint("fk_experiments_user_id", "experiments", type_="foreignkey")

    op.alter_column(
        "gene_sets",
        "user_id",
        type_=sa.String(36),
        existing_type=sa.CHAR(36),
        existing_nullable=True,
    )
    op.alter_column(
        "experiments",
        "user_id",
        type_=sa.String(36),
        existing_type=sa.CHAR(36),
        existing_nullable=True,
    )
