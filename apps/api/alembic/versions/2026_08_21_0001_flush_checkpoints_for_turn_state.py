"""Flush LangGraph checkpoints for the TurnState/StrategyDomainState split.

The checkpointed ``PipelineState`` moved its strategy fields under ``domain``,
so an old checkpoint no longer deserializes; the durable event log keeps every
transcript.

Revision ID: 2026_08_21_0001
Revises: 2026_08_19_0002
Create Date: 2026-08-21 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "2026_08_21_0001"
down_revision: str | Sequence[str] | None = "2026_08_19_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The checkpointer lifespan creates these tables, not alembic, so a database
# that has never run a turn has nothing to flush. ``checkpoint_migrations``
# holds the checkpointer's own DDL version and is left alone.
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
    """Irreversible: a flushed checkpoint cannot be reconstructed."""
