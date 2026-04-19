"""Drop the checkpoint_labels table.

Checkpoint-level labeling/pinning was the old branching UX — replaced by
conversation-level forks. No user-facing read path remains, so the table
goes too.

Revision ID: 2026_04_18_0006
Revises: 2026_04_18_0005
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2026_04_18_0006"
down_revision: str | Sequence[str] | None = "2026_04_18_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("checkpoint_labels_thread_idx", table_name="checkpoint_labels")
    op.drop_table("checkpoint_labels")


def downgrade() -> None:
    msg = "No backwards compat — this migration is one-way."
    raise NotImplementedError(msg)
