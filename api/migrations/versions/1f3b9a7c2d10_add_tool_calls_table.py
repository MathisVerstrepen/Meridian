# flake8: noqa
"""add tool_calls table

Revision ID: 1f3b9a7c2d10
Revises: a1f2d4e5c6b7
Create Date: 2026-03-12 11:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "1f3b9a7c2d10"
down_revision = "a1f2d4e5c6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_context_payload", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["graph_id"], ["graphs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tool_calls_user_id", "tool_calls", ["user_id"], unique=False)
    op.create_index(
        "idx_tool_calls_graph_node", "tool_calls", ["graph_id", "node_id"], unique=False
    )
    op.create_index("idx_tool_calls_model_id", "tool_calls", ["model_id"], unique=False)
    op.create_index("idx_tool_calls_created_at", "tool_calls", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_tool_calls_created_at", table_name="tool_calls")
    op.drop_index("idx_tool_calls_model_id", table_name="tool_calls")
    op.drop_index("idx_tool_calls_graph_node", table_name="tool_calls")
    op.drop_index("idx_tool_calls_user_id", table_name="tool_calls")
    op.drop_table("tool_calls")
