# flake8: noqa
"""add duration to tool calls

Revision ID: 9f4c1c2d7e8f
Revises: 6c3c9d7f1a2b
Create Date: 2026-04-19 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9f4c1c2d7e8f"
down_revision = "6c3c9d7f1a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tool_calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tool_calls", schema=None) as batch_op:
        batch_op.drop_column("duration_ms")
