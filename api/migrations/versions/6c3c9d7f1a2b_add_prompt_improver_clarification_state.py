"""add prompt improver clarification state

Revision ID: 6c3c9d7f1a2b
Revises: 2b0b7f3d9e21
Create Date: 2026-04-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6c3c9d7f1a2b"
down_revision = "2b0b7f3d9e21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prompt_improver_runs",
        sa.Column("active_phase", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "prompt_improver_runs",
        sa.Column("active_tool_call_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "prompt_improver_runs",
        sa.Column(
            "clarification_tool_call_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.alter_column(
        "prompt_improver_runs",
        "audit",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "prompt_improver_runs",
        "audit",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default="{}",
    )
    op.drop_column("prompt_improver_runs", "clarification_tool_call_ids")
    op.drop_column("prompt_improver_runs", "active_tool_call_id")
    op.drop_column("prompt_improver_runs", "active_phase")
