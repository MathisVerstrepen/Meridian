# flake8: noqa
"""add temporary column to graph

Revision ID: 8969e73ef9b7
Revises: 75bb67fb55db
Create Date: 2025-09-16 15:46:24.961746

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "8969e73ef9b7"
down_revision = "75bb67fb55db"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the 'temporary' column to the 'graph' table with a default value of False
    # temporary: bool = Field(default=False, nullable=False)
    op.add_column(
        "graphs",
        sa.Column("temporary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    pass


def downgrade() -> None:
    # Remove the 'temporary' column from the 'graph' table
    op.drop_column("graphs", "temporary")

    pass
