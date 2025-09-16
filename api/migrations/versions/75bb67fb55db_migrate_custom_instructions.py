# flake8: noqa
"""migrate custom_instructions

Revision ID: 75bb67fb55db
Revises: 794c66868cfa
Create Date: 2025-09-15 17:43:28.211187

"""

import json

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "75bb67fb55db"
down_revision = "794c66868cfa"
branch_labels = None
depends_on = None

default_systemPrompt = [
    {
        "id": "f342a558-5826-45cf-9b08-5f130414a4ab",
        "name": "Quality Helper",
        "prompt": "",
        "enabled": True,
        "editable": False,
        "reference": "QUALITY_HELPER_PROMPT",
    },
    {
        "id": "2be98df8-5815-4652-bef9-0435c9ced143",
        "name": "Mermaid Helper",
        "prompt": "",
        "enabled": True,
        "editable": False,
        "reference": "MERMAID_DIAGRAM_PROMPT",
    },
]

default_custom_instructions = [
    "f342a558-5826-45cf-9b08-5f130414a4ab",
    "2be98df8-5815-4652-bef9-0435c9ced143",
]


def upgrade() -> None:
    # Remove models.globalSystemPrompt key from settings_data json column of table settings
    op.execute(
        "UPDATE settings SET settings_data = settings_data - 'globalSystemPrompt' "
        "WHERE jsonb_typeof(settings_data) = 'object'"
    )

    # Set models.systemPrompt to default_systemPrompt for all users in settings_data json column of table settings
    op.execute(
        f"UPDATE settings SET settings_data = jsonb_set(settings_data, '{{models,systemPrompt}}', '{json.dumps(default_systemPrompt)}')"
    )

    # Clear custom_instructions column and change its type to JSONB array and set it to default_custom_instructions for all rows
    op.execute(
        f"UPDATE graphs SET custom_instructions = '{json.dumps(default_custom_instructions)}'::jsonb"
    )
    op.alter_column(
        "graphs",
        "custom_instructions",
        type_=sa.JSON,
        postgresql_using="custom_instructions::jsonb",
    )

    pass


def downgrade() -> None:
    # Add models.globalSystemPrompt key with empty array value to settings_data json column of table settings
    op.execute(
        "UPDATE settings SET settings_data = jsonb_set(settings_data, '{models,globalSystemPrompt}', '[]') "
        "WHERE jsonb_typeof(settings_data) = 'object'"
    )

    # Remove models.systemPrompt key from settings_data json column of table settings
    op.execute(
        "UPDATE settings SET settings_data = settings_data - 'systemPrompt' "
        "WHERE jsonb_typeof(settings_data) = 'object'"
    )

    # Change custom_instructions column type back to TEXT and set it to NULL for all rows
    op.alter_column(
        "graphs",
        "custom_instructions",
        type_=sa.Text,
        postgresql_using="NULL",
    )
    op.execute("UPDATE graphs SET custom_instructions = NULL")

    pass
