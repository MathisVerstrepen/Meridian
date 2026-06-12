# flake8: noqa
"""add image generation jobs

Revision ID: e5b7c9a2d4f1
Revises: 9f4c1c2d7e8f
Create Date: 2026-04-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e5b7c9a2d4f1"
down_revision = "9f4c1c2d7e8f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_generation_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("effective_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("aspect_ratio", sa.String(length=16), nullable=False),
        sa.Column("resolution", sa.String(length=16), nullable=False),
        sa.Column("style_preset", sa.String(length=64), nullable=True),
        sa.Column("source_image_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
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
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_image_generation_jobs_batch_id",
        "image_generation_jobs",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_image_generation_jobs_file_id",
        "image_generation_jobs",
        ["file_id"],
        unique=False,
    )
    op.create_index(
        "ix_image_generation_jobs_user_id",
        "image_generation_jobs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_image_generation_jobs_user_created",
        "image_generation_jobs",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_image_generation_jobs_batch_user",
        "image_generation_jobs",
        ["batch_id", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_image_generation_jobs_batch_user", table_name="image_generation_jobs")
    op.drop_index("idx_image_generation_jobs_user_created", table_name="image_generation_jobs")
    op.drop_index("ix_image_generation_jobs_user_id", table_name="image_generation_jobs")
    op.drop_index("ix_image_generation_jobs_file_id", table_name="image_generation_jobs")
    op.drop_index("ix_image_generation_jobs_batch_id", table_name="image_generation_jobs")
    op.drop_table("image_generation_jobs")
