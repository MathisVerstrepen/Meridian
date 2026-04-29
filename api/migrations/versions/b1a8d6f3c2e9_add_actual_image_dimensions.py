# flake8: noqa
"""add actual image dimensions

Revision ID: b1a8d6f3c2e9
Revises: e5b7c9a2d4f1
Create Date: 2026-04-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1a8d6f3c2e9"
down_revision = "e5b7c9a2d4f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("image_generation_jobs", sa.Column("actual_width", sa.Integer(), nullable=True))
    op.add_column("image_generation_jobs", sa.Column("actual_height", sa.Integer(), nullable=True))
    op.add_column(
        "image_generation_jobs",
        sa.Column("actual_aspect_ratio", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "actual_aspect_ratio")
    op.drop_column("image_generation_jobs", "actual_height")
    op.drop_column("image_generation_jobs", "actual_width")
