# flake8: noqa
"""add pinned column to graphs table

Revision ID: 700e47459df6
Revises: 8969e73ef9b7
Create Date: 2025-09-21 09:40:23.998822

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "700e47459df6"
down_revision = "8969e73ef9b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pinned column to graphs table
    # pinned: bool = Field(default=False, nullable=False)
    op.add_column(
        "graphs",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
    )

    pass


def downgrade() -> None:
    op.drop_column("graphs", "pinned")

    pass
