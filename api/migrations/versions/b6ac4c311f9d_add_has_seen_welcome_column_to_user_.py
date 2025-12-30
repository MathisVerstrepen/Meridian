# flake8: noqa
"""add has_seen_welcome column to user table

Revision ID: b6ac4c311f9d
Revises: 7a96dbc85d74
Create Date: 2025-12-30 17:22:45.613266

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "b6ac4c311f9d"
down_revision = "7a96dbc85d74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "has_seen_welcome",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.false(),
        ),
    )

    pass


def downgrade() -> None:

    op.drop_column("users", "has_seen_welcome")
    pass
