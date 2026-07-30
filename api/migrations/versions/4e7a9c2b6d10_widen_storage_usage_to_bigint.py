"""widen storage usage to bigint

Revision ID: 4e7a9c2b6d10
Revises: f3a6b7c8d9e0
Create Date: 2026-07-30 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4e7a9c2b6d10"
down_revision = "f3a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_storage_usage",
        "total_bytes_used",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "user_storage_usage",
        "total_bytes_used",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
