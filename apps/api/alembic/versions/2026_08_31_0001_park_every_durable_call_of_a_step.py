"""Flush every checkpoint: a parked durable call is now a list of calls.

One model step can hand several tool calls to the worker, so the parked state
records every durable call of the step instead of one, and the turn carries
every task's answer. A strict state does not read a shape written before that,
so every checkpoint goes. A flushed thread loses its graph state, its pending
approvals, its turn totals and a one-agent thread's message history, and
resumes from a fresh turn; conversations, the durable event log, messages,
strategies and background tasks are untouched.

Revision ID: 2026_08_31_0001
Revises: 2026_08_30_0003
Create Date: 2026-08-31 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "2026_08_31_0001"
down_revision: str | Sequence[str] | None = "2026_08_30_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The checkpointer lifespan creates these tables, not alembic, so a database
# that has never run a turn has nothing to flush.
_FLUSH_CHECKPOINTS = """
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'checkpoint_writes',
        'checkpoint_blobs',
        'checkpoints'
    ]
    LOOP
        IF to_regclass('public.' || tbl) IS NOT NULL THEN
            EXECUTE format('TRUNCATE TABLE %I', tbl);
        END IF;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_FLUSH_CHECKPOINTS)


def downgrade() -> None:
    op.execute(_FLUSH_CHECKPOINTS)
