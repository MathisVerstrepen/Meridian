# flake8: noqa
"""add prompt improver tables

Revision ID: 2b0b7f3d9e21
Revises: 1f3b9a7c2d10
Create Date: 2026-03-31 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2b0b7f3d9e21"
down_revision = "1f3b9a7c2d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_improver_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("target_node_id", sa.String(length=255), nullable=True),
        sa.Column(
            "target_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_prompt", sa.Text(), nullable=False),
        sa.Column(
            "source_template_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "selected_dimension_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "recommended_dimension_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "audit",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("improved_prompt", sa.Text(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["graph_id"], ["graphs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_run_id"], ["prompt_improver_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prompt_improver_runs_user_id", "prompt_improver_runs", ["user_id"])
    op.create_index(
        "idx_prompt_improver_runs_graph_node",
        "prompt_improver_runs",
        ["graph_id", "node_id"],
    )
    op.create_index(
        "idx_prompt_improver_runs_parent_run_id",
        "prompt_improver_runs",
        ["parent_run_id"],
    )
    op.create_index(
        "idx_prompt_improver_runs_created_at",
        "prompt_improver_runs",
        ["created_at"],
    )

    op.create_table(
        "prompt_improver_changes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("source_start", sa.Integer(), nullable=False),
        sa.Column("source_end", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("suggested_text", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("dimension_id", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["prompt_improver_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prompt_improver_changes_run_id", "prompt_improver_changes", ["run_id"])
    op.create_index(
        "idx_prompt_improver_changes_run_order",
        "prompt_improver_changes",
        ["run_id", "order_index"],
    )


def downgrade() -> None:
    op.drop_index("idx_prompt_improver_changes_run_order", table_name="prompt_improver_changes")
    op.drop_index("idx_prompt_improver_changes_run_id", table_name="prompt_improver_changes")
    op.drop_table("prompt_improver_changes")

    op.drop_index("idx_prompt_improver_runs_created_at", table_name="prompt_improver_runs")
    op.drop_index("idx_prompt_improver_runs_parent_run_id", table_name="prompt_improver_runs")
    op.drop_index("idx_prompt_improver_runs_graph_node", table_name="prompt_improver_runs")
    op.drop_index("idx_prompt_improver_runs_user_id", table_name="prompt_improver_runs")
    op.drop_table("prompt_improver_runs")
