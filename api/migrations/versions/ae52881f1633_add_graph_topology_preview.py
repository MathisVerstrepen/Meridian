"""add graph topology preview

Revision ID: ae52881f1633
Revises: 4e7a9c2b6d10
Create Date: 2026-08-31 20:31:58.900735

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "ae52881f1633"
down_revision = "4e7a9c2b6d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "graphs",
        sa.Column(
            "topology_preview",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.literal_column(
                '\'{"version":1,"width":1000,"height":600,' '"nodes":[],"edges":[]}\'::jsonb'
            ),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("graphs", "topology_preview")
