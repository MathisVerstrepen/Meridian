# flake8: noqa
"""add cascade to edges and ensure user relations

Revision ID: 7a96dbc85d74
Revises: 033d7a6291b3
Create Date: 2025-12-30 15:55:39.280288

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "7a96dbc85d74"
down_revision = "033d7a6291b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Edges: graph_id -> graphs.id
    # Drop existing constraint (assuming default naming convention)
    op.drop_constraint("edges_graph_id_fkey", "edges", type_="foreignkey")
    # Recreate with CASCADE
    op.create_foreign_key(
        "edges_graph_id_fkey",
        "edges",
        "graphs",
        ["graph_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. Graphs: user_id -> users.id
    op.drop_constraint("graphs_user_id_fkey", "graphs", type_="foreignkey")
    op.create_foreign_key(
        "graphs_user_id_fkey",
        "graphs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Folders: user_id -> users.id
    op.drop_constraint("folders_user_id_fkey", "folders", type_="foreignkey")
    op.create_foreign_key(
        "folders_user_id_fkey",
        "folders",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 4. Files: user_id -> users.id
    op.drop_constraint("files_user_id_fkey", "files", type_="foreignkey")
    op.create_foreign_key(
        "files_user_id_fkey",
        "files",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 1. Edges
    op.drop_constraint("edges_graph_id_fkey", "edges", type_="foreignkey")
    op.create_foreign_key("edges_graph_id_fkey", "edges", "graphs", ["graph_id"], ["id"])

    # 2. Graphs
    op.drop_constraint("graphs_user_id_fkey", "graphs", type_="foreignkey")
    op.create_foreign_key("graphs_user_id_fkey", "graphs", "users", ["user_id"], ["id"])

    # 3. Folders
    op.drop_constraint("folders_user_id_fkey", "folders", type_="foreignkey")
    op.create_foreign_key("folders_user_id_fkey", "folders", "users", ["user_id"], ["id"])

    # 4. Files
    op.drop_constraint("files_user_id_fkey", "files", type_="foreignkey")
    op.create_foreign_key("files_user_id_fkey", "files", "users", ["user_id"], ["id"])
