# flake8: noqa
"""add plan_type column

Revision ID: 3819a2743c6d
Revises: 700e47459df6
Create Date: 2025-09-22 11:57:58.335809

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "3819a2743c6d"
down_revision = "700e47459df6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column plan_type to table users
    # plan_type: str = Field(
    #     default="free", sa_column=Column(TEXT, nullable=False)
    # )  # Options: "admin", "premium", "free"
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "plan_type",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="free",
            )
        )

    # Add column is_admin to table users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.sql.expression.false(),
            )
        )

    pass


def downgrade() -> None:
    # Remove column plan_type from table users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("plan_type")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("is_admin")

    pass
