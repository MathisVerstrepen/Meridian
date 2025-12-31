# flake8: noqa
"""add missing delete on cascade

Revision ID: 033d7a6291b3
Revises: 4c92255b08f3
Create Date: 2025-12-30 15:49:12.777292

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "033d7a6291b3"
down_revision = "4c92255b08f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Settings
    op.drop_constraint("settings_user_id_fkey", "settings", type_="foreignkey")
    op.create_foreign_key(
        "settings_user_id_fkey",
        "settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. Prompt Templates
    op.drop_constraint("prompt_templates_user_id_fkey", "prompt_templates", type_="foreignkey")
    op.create_foreign_key(
        "prompt_templates_user_id_fkey",
        "prompt_templates",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Refresh Tokens
    op.drop_constraint("refresh_tokens_user_id_fkey", "refresh_tokens", type_="foreignkey")
    op.create_foreign_key(
        "refresh_tokens_user_id_fkey",
        "refresh_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 4. Provider Tokens
    op.drop_constraint("provider_tokens_user_id_fkey", "provider_tokens", type_="foreignkey")
    op.create_foreign_key(
        "provider_tokens_user_id_fkey",
        "provider_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 5. Repositories
    op.drop_constraint("repositories_user_id_fkey", "repositories", type_="foreignkey")
    op.create_foreign_key(
        "repositories_user_id_fkey",
        "repositories",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 6. User Query Usage
    op.drop_constraint("user_query_usage_user_id_fkey", "user_query_usage", type_="foreignkey")
    op.create_foreign_key(
        "user_query_usage_user_id_fkey",
        "user_query_usage",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 7. Used Refresh Tokens
    op.drop_constraint(
        "used_refresh_tokens_user_id_fkey", "used_refresh_tokens", type_="foreignkey"
    )
    op.create_foreign_key(
        "used_refresh_tokens_user_id_fkey",
        "used_refresh_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 8. Template Bookmarks (User ID)
    op.drop_constraint("template_bookmarks_user_id_fkey", "template_bookmarks", type_="foreignkey")
    op.create_foreign_key(
        "template_bookmarks_user_id_fkey",
        "template_bookmarks",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 9. Template Bookmarks (Template ID)
    op.drop_constraint(
        "template_bookmarks_template_id_fkey", "template_bookmarks", type_="foreignkey"
    )
    op.create_foreign_key(
        "template_bookmarks_template_id_fkey",
        "template_bookmarks",
        "prompt_templates",
        ["template_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # 1. Settings
    op.drop_constraint("settings_user_id_fkey", "settings", type_="foreignkey")
    op.create_foreign_key("settings_user_id_fkey", "settings", "users", ["user_id"], ["id"])

    # 2. Prompt Templates
    op.drop_constraint("prompt_templates_user_id_fkey", "prompt_templates", type_="foreignkey")
    op.create_foreign_key(
        "prompt_templates_user_id_fkey",
        "prompt_templates",
        "users",
        ["user_id"],
        ["id"],
    )

    # 3. Refresh Tokens
    op.drop_constraint("refresh_tokens_user_id_fkey", "refresh_tokens", type_="foreignkey")
    op.create_foreign_key(
        "refresh_tokens_user_id_fkey", "refresh_tokens", "users", ["user_id"], ["id"]
    )

    # 4. Provider Tokens
    op.drop_constraint("provider_tokens_user_id_fkey", "provider_tokens", type_="foreignkey")
    op.create_foreign_key(
        "provider_tokens_user_id_fkey", "provider_tokens", "users", ["user_id"], ["id"]
    )

    # 5. Repositories
    op.drop_constraint("repositories_user_id_fkey", "repositories", type_="foreignkey")
    op.create_foreign_key("repositories_user_id_fkey", "repositories", "users", ["user_id"], ["id"])

    # 6. User Query Usage
    op.drop_constraint("user_query_usage_user_id_fkey", "user_query_usage", type_="foreignkey")
    op.create_foreign_key(
        "user_query_usage_user_id_fkey",
        "user_query_usage",
        "users",
        ["user_id"],
        ["id"],
    )

    # 7. Used Refresh Tokens
    op.drop_constraint(
        "used_refresh_tokens_user_id_fkey", "used_refresh_tokens", type_="foreignkey"
    )
    op.create_foreign_key(
        "used_refresh_tokens_user_id_fkey",
        "used_refresh_tokens",
        "users",
        ["user_id"],
        ["id"],
    )

    # 8. Template Bookmarks (User ID)
    op.drop_constraint("template_bookmarks_user_id_fkey", "template_bookmarks", type_="foreignkey")
    op.create_foreign_key(
        "template_bookmarks_user_id_fkey",
        "template_bookmarks",
        "users",
        ["user_id"],
        ["id"],
    )

    # 9. Template Bookmarks (Template ID)
    op.drop_constraint(
        "template_bookmarks_template_id_fkey", "template_bookmarks", type_="foreignkey"
    )
    op.create_foreign_key(
        "template_bookmarks_template_id_fkey",
        "template_bookmarks",
        "prompt_templates",
        ["template_id"],
        ["id"],
    )
