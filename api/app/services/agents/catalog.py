"""Authorized read models for the private library and authenticated profile preview."""

from database.pg.agent_ops.tables import versions
from schemas.agents import AgentImport
from services.agents.library import describe, resolve_profile
from sqlalchemy import select


async def get_profile(engine, user_id, agent_id):
    async with engine.connect() as conn:
        row, _ = await resolve_profile(conn, user_id, agent_id)
        return await describe(conn, row, user_id)


async def export_profile(engine, user_id, agent_id):
    async with engine.connect() as conn:
        _, profile = await resolve_profile(conn, user_id, agent_id)
        return AgentImport(profile=profile)


async def list_versions(engine, user_id, agent_id):
    async with engine.connect() as conn:
        await resolve_profile(conn, user_id, agent_id, owned=True)
        return (
            (
                await conn.execute(
                    select(versions)
                    .where(versions.c.agent_id == agent_id)
                    .order_by(versions.c.version.desc())
                )
            )
            .mappings()
            .all()
        )
