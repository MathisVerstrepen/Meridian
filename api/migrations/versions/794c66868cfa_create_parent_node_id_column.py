"""create parent_node_id column

Revision ID: 794c66868cfa
Revises:
Create Date: 2025-09-08 16:53:23.887020

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "794c66868cfa"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add parent_node_id column to the nodes table
    # parent_node_id: Optional[str] = Field(default=None, max_length=255, nullable=True)
    op.add_column(
        "nodes",
        sa.Column("parent_node_id", sa.String(length=255), nullable=True),
    )

    pass


def downgrade() -> None:
    # Remove parent_node_id column from the nodes table
    op.drop_column("nodes", "parent_node_id")
    pass
