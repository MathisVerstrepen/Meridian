# flake8: noqa
"""replace mermaid prompt with tool

Revision ID: a1f2d4e5c6b7
Revises: fd447b227777
Create Date: 2026-03-11 11:00:00.000000

"""

import json

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1f2d4e5c6b7"
down_revision = "fd447b227777"
branch_labels = None
depends_on = None

default_tools_mermaid_generation = {
    "defaultModel": "anthropic/claude-haiku-4.5",
}

default_mermaid_helper = {
    "id": "2be98df8-5815-4652-bef9-0435c9ced143",
    "name": "Mermaid Helper",
    "prompt": "",
    "enabled": True,
    "editable": False,
    "reference": "MERMAID_DIAGRAM_PROMPT",
}


def upgrade() -> None:
    op.execute(
        """
        WITH mermaid_prompt_ids AS (
            SELECT
                s.user_id,
                array_agg(prompt->>'id') AS prompt_ids
            FROM settings AS s
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE
                    WHEN jsonb_typeof((s.settings_data)::jsonb->'models'->'systemPrompt') = 'array'
                        THEN (s.settings_data)::jsonb->'models'->'systemPrompt'
                    ELSE '[]'::jsonb
                END
            ) AS prompt
            WHERE COALESCE(prompt->>'reference', '') = 'MERMAID_DIAGRAM_PROMPT'
               OR COALESCE(prompt->>'name', '') = 'Mermaid Helper'
            GROUP BY s.user_id
        )
        UPDATE graphs AS g
        SET custom_instructions = COALESCE(
            (
                SELECT jsonb_agg(elem)
                FROM jsonb_array_elements(
                    CASE
                        WHEN jsonb_typeof((g.custom_instructions)::jsonb) = 'array'
                            THEN (g.custom_instructions)::jsonb
                        ELSE '[]'::jsonb
                    END
                ) AS elem
                WHERE NOT ((elem #>> '{}') = ANY(mermaid_prompt_ids.prompt_ids))
            ),
            '[]'::jsonb
        )::jsonb
        FROM mermaid_prompt_ids
        WHERE g.user_id = mermaid_prompt_ids.user_id
        """
    )

    op.execute(
        f"""
        UPDATE settings
        SET settings_data = jsonb_set(
            jsonb_set(
                (settings_data)::jsonb,
                '{{models,systemPrompt}}',
                COALESCE(
                    (
                        SELECT jsonb_agg(prompt)
                        FROM jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof((settings_data)::jsonb->'models'->'systemPrompt') = 'array'
                                    THEN (settings_data)::jsonb->'models'->'systemPrompt'
                                ELSE '[]'::jsonb
                            END
                        ) AS prompt
                        WHERE COALESCE(prompt->>'reference', '') <> 'MERMAID_DIAGRAM_PROMPT'
                          AND COALESCE(prompt->>'name', '') <> 'Mermaid Helper'
                    ),
                    '[]'::jsonb
                ),
                true
            ),
            '{{toolsMermaidGeneration}}',
            COALESCE(
                (settings_data)::jsonb->'toolsMermaidGeneration',
                '{json.dumps(default_tools_mermaid_generation)}'::jsonb
            ),
            true
        )::jsonb
        WHERE jsonb_typeof((settings_data)::jsonb) = 'object'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE settings
        SET settings_data = jsonb_set(
            (settings_data)::jsonb - 'toolsMermaidGeneration',
            '{{models,systemPrompt}}',
            (
                CASE
                    WHEN jsonb_typeof((settings_data)::jsonb->'models'->'systemPrompt') = 'array'
                        THEN (settings_data)::jsonb->'models'->'systemPrompt'
                    ELSE '[]'::jsonb
                END
            ) ||
            '{json.dumps([default_mermaid_helper])}'::jsonb,
            true
        )::jsonb
        WHERE jsonb_typeof((settings_data)::jsonb) = 'object'
          AND NOT EXISTS (
              SELECT 1
              FROM jsonb_array_elements(
                  CASE
                      WHEN jsonb_typeof((settings_data)::jsonb->'models'->'systemPrompt') = 'array'
                          THEN (settings_data)::jsonb->'models'->'systemPrompt'
                      ELSE '[]'::jsonb
                  END
              ) AS prompt
              WHERE COALESCE(prompt->>'reference', '') = 'MERMAID_DIAGRAM_PROMPT'
                 OR COALESCE(prompt->>'name', '') = 'Mermaid Helper'
          )
        """
    )
