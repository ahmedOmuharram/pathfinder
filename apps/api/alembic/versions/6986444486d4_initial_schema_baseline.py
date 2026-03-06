"""initial schema baseline

Revision ID: 6986444486d4
Revises:
Create Date: 2026-03-05 15:12:00.994909

Baseline migration: creates all tables from the current model definitions.
For existing databases, run `alembic stamp head` to mark as current.
For fresh databases, run `alembic upgrade head` to create the schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6986444486d4"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("external_id", sa.String(255), unique=True, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "control_sets",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255)),
        sa.Column("site_id", sa.String(100)),
        sa.Column("record_type", sa.String(100)),
        sa.Column("positive_ids", sa.JSON, server_default="[]"),
        sa.Column("negative_ids", sa.JSON, server_default="[]"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("tags", sa.JSON, server_default="[]"),
        sa.Column("provenance_notes", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("is_public", sa.Boolean, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_control_sets_site_id", "control_sets", ["site_id"])
    op.create_index("ix_control_sets_user_id", "control_sets", ["user_id"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("site_id", sa.String(100)),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("data", sa.JSON, server_default="{}"),
        sa.Column("batch_id", sa.String(50), nullable=True),
        sa.Column("benchmark_id", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_experiments_site_id", "experiments", ["site_id"])
    op.create_index("ix_experiments_user_id", "experiments", ["user_id"])
    op.create_index("ix_experiments_batch_id", "experiments", ["batch_id"])
    op.create_index("ix_experiments_benchmark_id", "experiments", ["benchmark_id"])

    op.create_table(
        "gene_sets",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("site_id", sa.String(100)),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("gene_ids", sa.JSON, server_default="[]"),
        sa.Column("source", sa.String(20), server_default="paste"),
        sa.Column("wdk_strategy_id", sa.Integer, nullable=True),
        sa.Column("wdk_step_id", sa.Integer, nullable=True),
        sa.Column("search_name", sa.String(255), nullable=True),
        sa.Column("record_type", sa.String(100), nullable=True),
        sa.Column("parameters", sa.JSON, nullable=True),
        sa.Column("parent_set_ids", sa.JSON, server_default="[]"),
        sa.Column("operation", sa.String(20), nullable=True),
        sa.Column("step_count", sa.Integer, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gene_sets_user_id", "gene_sets", ["user_id"])
    op.create_index("ix_gene_sets_site_id", "gene_sets", ["site_id"])
    op.create_index("ix_gene_sets_user_site", "gene_sets", ["user_id", "site_id"])

    op.create_table(
        "streams",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
        ),
        sa.Column("site_id", sa.String(50)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_streams_user_site", "streams", ["user_id", "site_id"])

    op.create_table(
        "stream_projections",
        sa.Column(
            "stream_id",
            sa.CHAR(36),
            sa.ForeignKey("streams.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("record_type", sa.String(100), nullable=True),
        sa.Column("wdk_strategy_id", sa.Integer, nullable=True),
        sa.Column("is_saved", sa.Boolean, server_default="false"),
        sa.Column("model_id", sa.String(100), nullable=True),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("step_count", sa.Integer, server_default="0"),
        sa.Column("plan", sa.JSON, server_default="{}"),
        sa.Column("steps", sa.JSON, server_default="[]"),
        sa.Column("root_step_id", sa.String(100), nullable=True),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("last_event_id", sa.String(30), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("site_id", sa.String(50), server_default=""),
    )
    op.create_index(
        "ix_proj_wdk",
        "stream_projections",
        ["wdk_strategy_id"],
        unique=True,
        postgresql_where=sa.text("wdk_strategy_id IS NOT NULL"),
    )

    op.create_table(
        "operations",
        sa.Column("operation_id", sa.String(32), primary_key=True),
        sa.Column(
            "stream_id",
            sa.CHAR(36),
            sa.ForeignKey("streams.id", ondelete="CASCADE"),
        ),
        sa.Column("type", sa.String(50)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ops_stream_status", "operations", ["stream_id", "status"])


def downgrade() -> None:
    op.drop_table("operations")
    op.drop_table("stream_projections")
    op.drop_table("streams")
    op.drop_table("gene_sets")
    op.drop_table("experiments")
    op.drop_table("control_sets")
    op.drop_table("users")
