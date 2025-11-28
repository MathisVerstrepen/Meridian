"""add folder suppoort for graphs

Revision ID: 35f1651611d7
Revises: 08b3c41d440c
Create Date: 2025-11-27 12:18:34.848009

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "35f1651611d7"
down_revision = "08b3c41d440c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the 'folders' table
    op.create_table(
        "folders",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("color", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_folders_user_id"), "folders", ["user_id"], unique=False)

    # Add the 'folder_id' column to the 'graphs' table
    op.add_column("graphs", sa.Column("folder_id", sa.UUID(as_uuid=True), nullable=True))

    # Create an index on the new column
    op.create_index(op.f("ix_graphs_folder_id"), "graphs", ["folder_id"], unique=False)

    # Create the foreign key constraint with ON DELETE SET NULL
    op.create_foreign_key(
        "fk_graphs_folder_id",  # Constraint name
        "graphs",  # Source table
        "folders",  # Remote table
        ["folder_id"],  # Local columns
        ["id"],  # Remote columns
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop the foreign key constraint from 'graphs'
    op.drop_constraint("fk_graphs_folder_id", "graphs", type_="foreignkey")

    # Drop the index and column from 'graphs'
    op.drop_index(op.f("ix_graphs_folder_id"), table_name="graphs")
    op.drop_column("graphs", "folder_id")

    # Drop the 'folders' table
    op.drop_index(op.f("ix_folders_user_id"), table_name="folders")
    op.drop_table("folders")
