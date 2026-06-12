"""add preview flag to image generation jobs

Revision ID: 9a7f4c2d1e6b
Revises: 8e4f2a9c6b31
Create Date: 2026-06-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9a7f4c2d1e6b"
down_revision = "8e4f2a9c6b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column("is_preview", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("image_generation_jobs", "is_preview", server_default=None)


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "is_preview")
