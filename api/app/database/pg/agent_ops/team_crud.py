"""Transactional provisioning of the account's permanent default Agent Team."""

import uuid

from database.pg.agent_ops.tables import memberships, teams
from database.pg.models import User
from sqlalchemy import func, insert, select


async def ensure_default_team(conn, user_id):
    user_id = uuid.UUID(str(user_id))
    # Serializes first use, profile creation and membership edits for one account.
    await conn.execute(select(User.id).where(User.id == user_id).with_for_update())
    team_id = (
        await conn.execute(
            select(teams.c.id).where(teams.c.owner_id == user_id, teams.c.is_default.is_(True))
        )
    ).scalar_one_or_none()
    if team_id is None:
        team_id = uuid.uuid4()
        await conn.execute(
            insert(teams).values(
                id=team_id,
                owner_id=user_id,
                name="Default Team",
                handle="default",
                description="New Agents are added here automatically.",
                is_default=True,
            )
        )
    return team_id


async def add_to_default_team(conn, user_id, agent_id):
    team_id = await ensure_default_team(conn, user_id)
    position = (
        await conn.execute(
            select(func.max(memberships.c.position)).where(memberships.c.team_id == team_id)
        )
    ).scalar_one()
    await conn.execute(
        insert(memberships).values(
            team_id=team_id, agent_id=agent_id, position=0 if position is None else position + 1
        )
    )
    return team_id
