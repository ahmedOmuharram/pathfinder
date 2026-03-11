"""add gene_set_id and gene_set_auto_imported to stream_projections

Revision ID: a3f1b2c4d5e6
Revises: 87d93def2ccd
Create Date: 2026-03-11 00:00:00.000000

Adds the strategy-to-gene-set association columns:
- gene_set_id: FK to gene_sets with ON DELETE SET NULL
- gene_set_auto_imported: one-way latch preventing regeneration after deletion
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1b2c4d5e6"
down_revision: str | Sequence[str] | None = "87d93def2ccd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_projections",
        sa.Column(
            "gene_set_id",
            sa.String(50),
            sa.ForeignKey("gene_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "stream_projections",
        sa.Column(
            "gene_set_auto_imported",
            sa.Boolean,
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("stream_projections", "gene_set_auto_imported")
    op.drop_column("stream_projections", "gene_set_id")
