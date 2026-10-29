"""Persist account default Teams and Team mention handles."""

import re
import unicodedata
import uuid

import sqlalchemy as sa
from alembic import op

revision = "c7b9e12d6a30"
down_revision = "a8e6f2c9d401"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_teams", sa.Column("handle", sa.String(50), nullable=True))
    op.add_column(
        "agent_teams",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    conn = op.get_bind()
    used = {}
    for row in conn.execute(
        sa.text("SELECT id, owner_id, name FROM agent_teams ORDER BY updated_at, id")
    ):
        normalized = (
            unicodedata.normalize("NFKD", row.name).encode("ascii", "ignore").decode().lower()
        )
        base = re.sub(r"[^a-z0-9_-]+", "-", normalized).strip("-") or "team"
        if not base[0].isalpha():
            base = "team-" + base
        if len(base) < 2:
            base += "-team"
        base = base[:50]
        taken = used.setdefault(row.owner_id, {"default"})
        handle, suffix = base, 2
        while handle in taken:
            ending = f"-{suffix}"
            handle = base[: 50 - len(ending)] + ending
            suffix += 1
        taken.add(handle)
        conn.execute(
            sa.text("UPDATE agent_teams SET handle = :handle WHERE id = :id"),
            {"handle": handle, "id": row.id},
        )
    op.alter_column("agent_teams", "handle", nullable=False)
    op.create_unique_constraint("agent_teams_owner_handle", "agent_teams", ["owner_id", "handle"])
    op.create_index(
        "agent_teams_one_default_per_owner",
        "agent_teams",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE"),
    )
    for user_id in conn.execute(sa.text("SELECT id FROM users")).scalars():
        team_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO agent_teams (id, owner_id, name, description, handle, is_default) "
                "VALUES (:id, :owner, 'Default Team', "
                "'New Agents are added here automatically.', 'default', true)"
            ),
            {"id": team_id, "owner": user_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO agent_team_members (team_id, agent_id, position) "
                "SELECT :team, id, row_number() OVER (ORDER BY created_at, id) - 1 "
                "FROM agent_profiles WHERE owner_id = :owner"
            ),
            {"team": team_id, "owner": user_id},
        )


def downgrade():
    op.drop_index("agent_teams_one_default_per_owner", table_name="agent_teams")
    op.drop_constraint("agent_teams_owner_handle", "agent_teams", type_="unique")
    op.drop_column("agent_teams", "is_default")
    op.drop_column("agent_teams", "handle")
