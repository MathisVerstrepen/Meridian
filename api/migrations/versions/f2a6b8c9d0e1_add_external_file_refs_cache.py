# flake8: noqa
"""add external file refs cache

Revision ID: f2a6b8c9d0e1
Revises: 9a7f4c2d1e6b
Create Date: 2026-06-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2a6b8c9d0e1"
down_revision: Union[str, None] = "9a7f4c2d1e6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_file_refs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("modified_time", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("md5_checksum", sa.Text(), nullable=True),
        sa.Column("web_view_link", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_file_refs_user_id", "external_file_refs", ["user_id"])
    op.create_index("ix_external_file_refs_provider", "external_file_refs", ["provider"])
    op.create_index(
        "idx_external_file_refs_user_provider_external",
        "external_file_refs",
        ["user_id", "provider", "external_id"],
        unique=True,
    )

    op.create_table(
        "external_file_cache",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("external_file_ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "last_accessed_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["external_file_ref_id"], ["external_file_refs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_file_cache_external_file_ref_id",
        "external_file_cache",
        ["external_file_ref_id"],
    )
    op.create_index("ix_external_file_cache_user_id", "external_file_cache", ["user_id"])
    op.create_index("ix_external_file_cache_content_hash", "external_file_cache", ["content_hash"])
    op.create_index(
        "idx_external_file_cache_ref_expires",
        "external_file_cache",
        ["external_file_ref_id", "expires_at"],
    )
    op.create_index(
        "idx_external_file_cache_user_expires",
        "external_file_cache",
        ["user_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_external_file_cache_user_expires", table_name="external_file_cache")
    op.drop_index("idx_external_file_cache_ref_expires", table_name="external_file_cache")
    op.drop_index("ix_external_file_cache_content_hash", table_name="external_file_cache")
    op.drop_index("ix_external_file_cache_user_id", table_name="external_file_cache")
    op.drop_index("ix_external_file_cache_external_file_ref_id", table_name="external_file_cache")
    op.drop_table("external_file_cache")
    op.drop_index("idx_external_file_refs_user_provider_external", table_name="external_file_refs")
    op.drop_index("ix_external_file_refs_provider", table_name="external_file_refs")
    op.drop_index("ix_external_file_refs_user_id", table_name="external_file_refs")
    op.drop_table("external_file_refs")
