"""add_pgvector_extension

Revision ID: c832cac9ff78
Revises: 7071adf96d33
Create Date: 2026-04-14 12:11:28.062402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


import pathfinder.persistence.models  # custom SQLAlchemy types (GUID, ...)

# revision identifiers, used by Alembic.
revision: str = 'c832cac9ff78'
down_revision: Union[str, Sequence[str], None] = '7071adf96d33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS vector")
