# flake8: noqa
"""add video generation job fields

Revision ID: c4d8e9f1a2b3
Revises: b1a8d6f3c2e9
Create Date: 2026-05-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4d8e9f1a2b3"
down_revision = "b1a8d6f3c2e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column("media_type", sa.String(length=16), nullable=False, server_default="image"),
    )
    op.add_column("image_generation_jobs", sa.Column("duration", sa.Integer(), nullable=True))
    op.alter_column("image_generation_jobs", "media_type", server_default=None)


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "duration")
    op.drop_column("image_generation_jobs", "media_type")
