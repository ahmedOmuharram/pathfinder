"""Clear LangGraph checkpoints for the FRAME->BUILD->VERIFY cutover.

The destructive pipeline migration removed PipelineState fields (problem_frame,
active_plan, plan_slot_answers, rescope_requested), deleted phase nodes/roles,
and dropped the submit_plan_for_approval deferred tool. Any in-flight thread
checkpointed mid-interrupt on the old machinery cannot be resumed under the new
graph. Truncate the checkpoint tables so every thread starts fresh; the durable
``messages`` table (conversation history) is untouched.

Revision ID: 2026_06_24_0001
Revises: 2026_05_07_0001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2026_06_24_0001"
down_revision: str | Sequence[str] | None = "2026_05_07_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLEAR_CHECKPOINTS = """
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'checkpoints'
    ) THEN
        EXECUTE 'TRUNCATE TABLE checkpoints, checkpoint_blobs, checkpoint_writes';
    END IF;
END $$;
"""


def upgrade() -> None:
    op.execute(_CLEAR_CHECKPOINTS)


def downgrade() -> None:
    msg = "No backwards compat — checkpoints cannot be reconstructed."
    raise NotImplementedError(msg)
