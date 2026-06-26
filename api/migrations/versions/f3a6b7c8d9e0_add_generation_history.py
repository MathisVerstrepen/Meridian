# flake8: noqa
"""add generation history

Revision ID: f3a6b7c8d9e0
Revises: e2a9b7c4d5f6
Create Date: 2026-06-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f3a6b7c8d9e0"
down_revision = "e2a9b7c4d5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("node_type", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column(
            "selected_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("preview", sa.Text(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["graph_id", "node_id"],
            ["nodes.graph_id", "nodes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_generation_history_user_id", "generation_history", ["user_id"])
    op.create_index(
        "idx_generation_history_graph_node_created",
        "generation_history",
        ["graph_id", "node_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_generation_history_graph_node_created", table_name="generation_history")
    op.drop_index("idx_generation_history_user_id", table_name="generation_history")
    op.drop_table("generation_history")
