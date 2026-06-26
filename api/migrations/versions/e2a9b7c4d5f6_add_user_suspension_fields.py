"""add user suspension fields

Revision ID: e2a9b7c4d5f6
Revises: 9a7f4c2d1e6b
Create Date: 2026-06-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e2a9b7c4d5f6"
down_revision = "9a7f4c2d1e6b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("suspended_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("suspended_until", sa.TIMESTAMP(timezone=True), nullable=True))
    op.alter_column("users", "is_suspended", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "suspended_until")
    op.drop_column("users", "suspended_reason")
    op.drop_column("users", "is_suspended")
