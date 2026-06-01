"""Rename conversations.plan → conversations.strategy_ast.

The column stored the *executed strategy AST* (a StrategyAst payload), not the
planning-agent's PlanArtifact. Renaming to kill the ambiguity.

Revision ID: 2026_04_18_0001
Revises: 2026_04_17_0001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2026_04_18_0001"
down_revision: str | Sequence[str] | None = "2026_04_17_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("conversations", "plan", new_column_name="strategy_ast")


def downgrade() -> None:
    msg = "No backwards compat — this migration is one-way."
    raise NotImplementedError(msg)
