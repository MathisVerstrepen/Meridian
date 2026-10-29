"""Private Team management, default provisioning and authenticated Team mentions."""

import re
import unicodedata
import uuid

from database.pg.agent_ops.tables import memberships, teams
from database.pg.agent_ops.team_crud import ensure_default_team
from schemas.agents import TeamWrite
from services.agents.library import fail, resolve_profile
from sqlalchemy import delete, func, insert, select, update


async def resolve_team(conn, user_id, team_id):
    row = (
        (
            await conn.execute(
                select(teams).where(teams.c.id == team_id, teams.c.owner_id == user_id)
            )
        )
        .mappings()
        .first()
    )
    if not row:
        fail("Team not found in your library.", 404)
    ids = (
        (
            await conn.execute(
                select(memberships.c.agent_id)
                .where(memberships.c.team_id == team_id)
                .order_by(memberships.c.position)
            )
        )
        .scalars()
        .all()
    )
    return {**row, "members": list(ids)}


async def list_teams(engine, user_id):
    async with engine.begin() as conn:
        await ensure_default_team(conn, user_id)
        ids = await conn.execute(
            select(teams.c.id)
            .where(teams.c.owner_id == user_id)
            .order_by(teams.c.is_default.desc(), teams.c.name, teams.c.id)
        )
        return [await resolve_team(conn, user_id, team_id) for team_id in ids.scalars()]


def suggest_team_handle(name):
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    handle = re.sub(r"[^a-z0-9_-]+", "-", normalized).strip("-") or "team"
    if not handle[0].isalpha():
        handle = "team-" + handle
    if len(handle) < 2:
        handle += "-team"
    return handle[:50]


async def save_team(engine, user_id, data: TeamWrite, team_id=None):
    async with engine.begin() as conn:
        await ensure_default_team(conn, user_id)
        previous = await resolve_team(conn, user_id, team_id) if team_id else None
        for agent_id in data.members:
            await resolve_profile(conn, user_id, agent_id, owned=True)
        handle = data.handle or (previous["handle"] if previous else suggest_team_handle(data.name))
        if previous and previous["is_default"] and handle != "default":
            fail("The default Team always uses @default.")
        base, suffix = handle, 2
        while (
            await conn.execute(
                select(teams.c.id).where(
                    teams.c.owner_id == user_id,
                    teams.c.handle == handle,
                    teams.c.id != team_id if team_id else teams.c.id.is_not(None),
                )
            )
        ).first():
            if data.handle:
                fail("A Team with this handle already exists.", 409)
            ending = f"-{suffix}"
            handle = base[: 50 - len(ending)] + ending
            suffix += 1
        values = dict(
            name=data.name, description=data.description, handle=handle, updated_at=func.now()
        )
        if team_id:
            await conn.execute(update(teams).where(teams.c.id == team_id).values(**values))
            await conn.execute(delete(memberships).where(memberships.c.team_id == team_id))
        else:
            team_id = uuid.uuid4()
            await conn.execute(insert(teams).values(id=team_id, owner_id=user_id, **values))
        for position, agent_id in enumerate(data.members):
            await conn.execute(
                insert(memberships).values(team_id=team_id, agent_id=agent_id, position=position)
            )
        return await resolve_team(conn, user_id, team_id)


async def resolve_mention(engine, user_id, message):
    match = re.match(r"^\s*@([a-zA-Z0-9_-]+)(?=\s|$)", message)
    if not match:
        if message.lstrip().startswith("@"):
            fail("Use one leading @team-handle to select a Team.")
        return {"team_id": None, "message": message}
    remaining = message[match.end() :].lstrip()
    if remaining.startswith("@"):
        fail("Only one leading Team mention is allowed.")
    async with engine.begin() as conn:
        await ensure_default_team(conn, user_id)
        team_id = (
            await conn.execute(
                select(teams.c.id).where(
                    teams.c.owner_id == user_id, teams.c.handle == match[1].lower()
                )
            )
        ).scalar_one_or_none()
        if team_id is None:
            fail("Unknown Team handle in your library.", 404)
    return {"team_id": str(team_id), "message": remaining}


async def configure_agent_nodes(conn, user_id, nodes):
    agent_nodes = [node for node in nodes if node.type == "agent"]
    if not agent_nodes:
        return
    default_id = await ensure_default_team(conn, user_id)
    for node in agent_nodes:
        data = dict(node.data or {})
        if "agentIds" in data or "primaryAgentId" in data:
            fail("Agent nodes select a Team only. Refresh the graph and choose a Team.", 422)
        team_id = data.get("teamId") or str(default_id)
        try:
            team_uuid = uuid.UUID(str(team_id))
        except ValueError:
            fail("Choose a valid Team for this Agent node.")
        await resolve_team(conn, user_id, team_uuid)
        node.data = {**data, "teamId": str(team_uuid)}
