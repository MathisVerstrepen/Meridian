"""create UserQueryUsage table

Revision ID: 08b3c41d440c
Revises: 4075d92afec6
Create Date: 2025-10-21 21:45:26.650964

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "08b3c41d440c"
down_revision = "4075d92afec6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_query_usage",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("query_type", sa.String(length=50), nullable=False, index=True),
        sa.Column("used_queries", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "billing_period_start",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("billing_period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_user_query_usage_user_id_query_type",
        "user_query_usage",
        ["user_id", "query_type"],
        unique=True,
    )

    pass


def downgrade() -> None:
    op.drop_index("idx_user_query_usage_user_id_query_type", table_name="user_query_usage")
    op.drop_table("user_query_usage")

    pass
