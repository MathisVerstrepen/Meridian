# flake8: noqa
"""add content_hash column

Revision ID: 4075d92afec6
Revises: 3819a2743c6d
Create Date: 2025-10-03 15:16:41.319024

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "4075d92afec6"
down_revision = "3819a2743c6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("content_hash", sa.TEXT(), nullable=True, index=True))
    pass


def downgrade() -> None:
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.drop_column("content_hash")

    pass
