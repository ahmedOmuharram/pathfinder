"""drop legacy chat tables (event-sourcing era)

Deletes `stream_projections`, `streams`, `operations`, and `strategy_plans`
— the tables that backed the old Redis-Streams + `finish_*`-tool chat
architecture. New chat uses the `messages` + `chats` tables (added in the
previous migration) + pydantic-ai's VercelAIAdapter in-memory pipeline.

The downgrade is intentionally not supported because these tables held
event-sourcing data that is gone — recovery requires a backup dump.

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-04-13
"""

from __future__ import annotations

from alembic import op


revision = "i4j5k6l7m8n9"
down_revision = "h3i4j5k6l7m8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK-aware drop order: tables referencing others get dropped first.
    op.execute("DROP TABLE IF EXISTS stream_projections CASCADE;")
    op.execute("DROP TABLE IF EXISTS streams CASCADE;")
    op.execute("DROP TABLE IF EXISTS operations CASCADE;")
    op.execute("DROP TABLE IF EXISTS strategy_plans CASCADE;")


def downgrade() -> None:
    raise NotImplementedError(
        "Cannot recreate legacy chat tables — restore from backup if needed."
    )
