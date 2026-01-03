# flake8: noqa
"""add workspace table

Revision ID: fd447b227777
Revises: c8c2d84a3b86
Create Date: 2026-01-02 17:26:53.779164

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fd447b227777"
down_revision = "c8c2d84a3b86"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
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

    # 2. Add workspace_id to folders
    op.add_column(
        "folders", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_folders_workspace_id",
        "folders",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Add workspace_id to graphs
    op.add_column("graphs", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_graphs_workspace_id",
        "graphs",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Data Migration
    # Create default workspaces for all existing users
    op.execute(
        """
        INSERT INTO workspaces (id, user_id, name, created_at, updated_at)
        SELECT uuid_generate_v4(), id, 'Default', now(), now()
        FROM users
    """
    )

    # Link existing folders to the new default workspace of their owner
    op.execute(
        """
        UPDATE folders f
        SET workspace_id = w.id
        FROM workspaces w
        WHERE f.user_id = w.user_id
    """
    )

    # Link existing graphs to the new default workspace of their owner
    op.execute(
        """
        UPDATE graphs g
        SET workspace_id = w.id
        FROM workspaces w
        WHERE g.user_id = w.user_id
    """
    )


def downgrade() -> None:
    # 1. Drop foreign keys and columns
    op.drop_constraint("fk_graphs_workspace_id", "graphs", type_="foreignkey")
    op.drop_column("graphs", "workspace_id")

    op.drop_constraint("fk_folders_workspace_id", "folders", type_="foreignkey")
    op.drop_column("folders", "workspace_id")

    # 2. Drop workspaces table
    op.drop_table("workspaces")
