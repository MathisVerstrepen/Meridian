"""add email verification token

Revision ID: 4c92255b08f3
Revises: cc9210764545
Create Date: 2025-12-30 10:18:16.293677

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "4c92255b08f3"
down_revision = "cc9210764545"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_verified column to users table
    # server_default is required to populate existing rows with 'false'
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # Create verification_tokens table
    op.create_table(
        "verification_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for performance
    op.create_index(
        op.f("ix_verification_tokens_email"), "verification_tokens", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_verification_tokens_user_id"), "verification_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_verification_tokens_user_id"), table_name="verification_tokens")
    op.drop_index(op.f("ix_verification_tokens_email"), table_name="verification_tokens")

    # Drop table
    op.drop_table("verification_tokens")

    # Drop column
    op.drop_column("users", "is_verified")
