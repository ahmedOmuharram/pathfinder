"""Flush LangGraph checkpoints written before FRAME/BUILD/VERIFY.

``PipelineState`` is now strict (``extra="forbid"``). Any checkpoint still
carrying the five-phase shape -- ``active_plan``, ``discovery_section``,
``plan_section`` -- fails validation on resume, which is the intended
behaviour: a renamed or removed field should be loud, not silently dropped.

That only works if no such checkpoint survives, so this flushes them. The
alternative was leaving ``extra`` permissive, which keeps a compatibility
shim alive for a shape nothing writes any more and hides the next rename
the same way.

In-flight conversations resume from a fresh turn. PathFinder has not
shipped, so there is no production history to preserve.

Revision ID: 2026_08_09_0001
Revises: 2026_08_08_0002
Create Date: 2026-08-09 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "2026_08_09_0001"
down_revision: str | Sequence[str] | None = "2026_08_08_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            tbl text;
        BEGIN
            FOREACH tbl IN ARRAY ARRAY[
                'checkpoint_writes',
                'checkpoint_blobs',
                'checkpoints',
                'checkpoint_labels'
            ]
            LOOP
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = tbl
                ) THEN
                    EXECUTE format('TRUNCATE TABLE %I RESTART IDENTITY', tbl);
                END IF;
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    """Irreversible: the flushed checkpoints are not recoverable."""
