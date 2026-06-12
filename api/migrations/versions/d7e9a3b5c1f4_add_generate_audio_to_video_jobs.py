"""add generate audio to video jobs

Revision ID: d7e9a3b5c1f4
Revises: c4d8e9f1a2b3
Create Date: 2026-05-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d7e9a3b5c1f4"
down_revision = "c4d8e9f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_generation_jobs",
        sa.Column("generate_audio", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("image_generation_jobs", "generate_audio", server_default=None)


def downgrade() -> None:
    op.drop_column("image_generation_jobs", "generate_audio")
