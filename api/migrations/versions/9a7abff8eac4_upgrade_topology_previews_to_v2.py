"""upgrade topology previews to v2

Revision ID: 9a7abff8eac4
Revises: ae52881f1633
Create Date: 2026-09-01 14:41:35.871132

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9a7abff8eac4"
down_revision = "ae52881f1633"
branch_labels = None
depends_on = None

EMPTY_V1_SQL = '\'{"version":1,"width":1000,"height":600,"nodes":[],"edges":[]}\'::jsonb'
EMPTY_V2_SQL = '\'{"version":2,"width":1000,"height":600,"nodes":[],"edges":[]}\'::jsonb'


def _reset_statement(empty_preview_sql: str) -> sa.Update:
    graphs = sa.table(
        "graphs",
        sa.column("topology_preview", postgresql.JSONB()),
    )
    return sa.update(graphs).values(
        topology_preview=sa.literal_column(empty_preview_sql),
    )


def upgrade() -> None:
    op.alter_column(
        "graphs",
        "topology_preview",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        server_default=sa.literal_column(EMPTY_V2_SQL),
    )
    op.execute(_reset_statement(EMPTY_V2_SQL))


def downgrade() -> None:
    op.alter_column(
        "graphs",
        "topology_preview",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        server_default=sa.literal_column(EMPTY_V1_SQL),
    )
    op.execute(_reset_statement(EMPTY_V1_SQL))
