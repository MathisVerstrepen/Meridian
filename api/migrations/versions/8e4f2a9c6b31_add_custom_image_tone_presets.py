# flake8: noqa
"""add custom image tone presets

Revision ID: 8e4f2a9c6b31
Revises: d7e9a3b5c1f4
Create Date: 2026-06-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8e4f2a9c6b31"
down_revision = "d7e9a3b5c1f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_image_tone_presets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=48), nullable=False),
        sa.Column("suffix", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["image_id"], ["files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_custom_image_tone_presets_image_id",
        "custom_image_tone_presets",
        ["image_id"],
        unique=False,
    )
    op.create_index(
        "ix_custom_image_tone_presets_user_id",
        "custom_image_tone_presets",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_custom_image_tone_presets_user_created",
        "custom_image_tone_presets",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_custom_image_tone_presets_user_created",
        table_name="custom_image_tone_presets",
    )
    op.drop_index(
        "ix_custom_image_tone_presets_user_id",
        table_name="custom_image_tone_presets",
    )
    op.drop_index(
        "ix_custom_image_tone_presets_image_id",
        table_name="custom_image_tone_presets",
    )
    op.drop_table("custom_image_tone_presets")
