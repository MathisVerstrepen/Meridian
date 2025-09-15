"""migrate custom_instructions

Revision ID: 75bb67fb55db
Revises: 794c66868cfa
Create Date: 2025-09-15 17:43:28.211187

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "75bb67fb55db"
down_revision = "794c66868cfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clear custom_instructions column and change its type to JSONB array
    # custom_instructions: Optional[list[str]] = Field(
    #     default=None, sa_column=Column(JSONB, nullable=True)
    # )
    op.execute("UPDATE graphs SET custom_instructions = '[]'::jsonb")
    op.alter_column(
        "graphs",
        "custom_instructions",
        type_=sa.JSON,
        postgresql_using="custom_instructions::jsonb",
    )

    pass


def downgrade() -> None:
    op.execute(
        "UPDATE graphs SET custom_instructions = NULL WHERE custom_instructions = '[]'::jsonb"
    )
    op.alter_column(
        "graphs",
        "custom_instructions",
        type_=sa.TEXT,
        postgresql_using="custom_instructions::text",
    )

    pass
