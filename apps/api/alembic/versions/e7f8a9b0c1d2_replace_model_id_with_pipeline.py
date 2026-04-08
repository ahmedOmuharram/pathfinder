"""replace model_id with pipeline on stream_projections

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-04-07 00:00:00.000000

Drop the single model_id column and add a JSON pipeline column that stores
per-phase model configuration (discovery, planning, execution, verification).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stream_projections",
        sa.Column("pipeline", sa.JSON(), nullable=True),
    )
    op.drop_column("stream_projections", "model_id")


def downgrade() -> None:
    op.add_column(
        "stream_projections",
        sa.Column("model_id", sa.String(100), nullable=True),
    )
    op.drop_column("stream_projections", "pipeline")
