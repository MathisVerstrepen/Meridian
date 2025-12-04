# flake8: noqa
"""add bookmarks for templates

Revision ID: cc9210764545
Revises: d2f8cf93efd3
Create Date: 2025-12-03 19:22:04.602849

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "cc9210764545"
down_revision = "d2f8cf93efd3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_bookmarks",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["prompt_templates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("user_id", "template_id"),
    )

    op.add_column(
        "prompt_templates",
        sa.Column("order_index", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("template_bookmarks")
