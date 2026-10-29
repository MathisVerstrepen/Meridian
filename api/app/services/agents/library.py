import uuid
from datetime import datetime, timezone

from database.pg.agent_ops.tables import (
    agents,
    bookmarks,
    memberships,
    ratings,
    usage,
    versions,
)
from database.pg.agent_ops.team_crud import add_to_default_team, ensure_default_team
from database.pg.models import User
from fastapi import HTTPException
from schemas.agents import AgentWrite
from sqlalchemy import delete, exists, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert


def fail(message, status=400):
    raise HTTPException(status_code=status, detail=message)


async def resolve_profile(conn, user_id, agent_id, *, execute=False, owned=False):
    row = (await conn.execute(select(agents).where(agents.c.id == agent_id))).mappings().first()
    if not row:
        fail("Agent not found.", 404)
    own = str(row["owner_id"]) == str(user_id)
    profile = AgentWrite.model_validate(row["profile"])
    if not own and (
        owned or execute or profile.visibility != "public" or profile.lifecycle != "active"
    ):
        fail("Agent not found in your library. Fork it before use.", 404)
    if execute and profile.lifecycle != "active":
        fail("Activate or restore this Agent before executing it.")
    return dict(row), profile


async def describe(conn, row, user_id):
    author = (await conn.execute(select(User.username).where(User.id == row["owner_id"]))).scalar()
    stats = (
        await conn.execute(
            select(func.count(), func.avg(ratings.c.value)).where(ratings.c.agent_id == row["id"])
        )
    ).first()
    return {
        **row,
        "author": author,
        "rating_count": stats[0],
        "rating_average": float(stats[1] or 0),
        "bookmark_count": (
            await conn.execute(
                select(func.count()).select_from(bookmarks).where(bookmarks.c.agent_id == row["id"])
            )
        ).scalar(),
        "fork_count": (
            await conn.execute(
                select(func.count()).select_from(agents).where(agents.c.source_id == row["id"])
            )
        ).scalar(),
        "usage_count": (
            await conn.execute(
                select(func.count()).select_from(usage).where(usage.c.agent_id == row["id"])
            )
        ).scalar(),
        "bookmarked": bool(
            (
                await conn.execute(
                    select(bookmarks.c.agent_id).where(
                        bookmarks.c.agent_id == row["id"], bookmarks.c.user_id == user_id
                    )
                )
            ).first()
        ),
        "my_rating": (
            await conn.execute(
                select(ratings.c.value).where(
                    ratings.c.agent_id == row["id"], ratings.c.user_id == user_id
                )
            )
        ).scalar(),
    }


async def save_profile(engine, user_id, data, agent_id=None, *, source=None):
    user_id = uuid.UUID(str(user_id))
    payload = data.model_dump(mode="json")
    async with engine.begin() as conn:
        if not agent_id:
            await ensure_default_team(conn, user_id)
        if agent_id:
            await conn.execute(select(agents.c.id).where(agents.c.id == agent_id).with_for_update())
            row, _ = await resolve_profile(conn, user_id, agent_id, owned=True)
            version = row["version"] + 1
        else:
            agent_id, version = uuid.uuid4(), 1
        collision = (
            await conn.execute(
                select(agents.c.id).where(
                    agents.c.owner_id == user_id,
                    agents.c.handle == data.handle,
                    agents.c.id != agent_id,
                )
            )
        ).first()
        if collision:
            fail("An Agent with this handle already exists.", 409)
        values = dict(
            handle=data.handle,
            profile=payload,
            version=version,
            updated_at=datetime.now(timezone.utc),
            verified=False,
        )
        if version == 1:
            values.update(id=agent_id, owner_id=user_id)
            if source:
                values.update(source_id=source["id"], source_version=source["version"])
            await conn.execute(insert(agents).values(**values))
            await add_to_default_team(conn, user_id, agent_id)
        else:
            await conn.execute(update(agents).where(agents.c.id == agent_id).values(**values))
        await conn.execute(
            insert(versions).values(agent_id=agent_id, version=version, profile=payload)
        )
        row, _ = await resolve_profile(conn, user_id, agent_id)
        return await describe(conn, row, user_id)


async def list_profiles(
    engine,
    user_id,
    *,
    view="my",
    q="",
    category="",
    model="",
    tool="",
    sort="updated",
    offset=0,
    limit=24,
):
    user_id = uuid.UUID(str(user_id))
    p = agents.c.profile
    public = (p["visibility"].astext == "public") & (p["lifecycle"].astext == "active")
    visible = or_(agents.c.owner_id == user_id, public)
    condition = agents.c.owner_id == user_id
    if view == "marketplace":
        condition = public
    elif view == "bookmarked":
        condition = (
            exists(
                select(bookmarks).where(
                    bookmarks.c.agent_id == agents.c.id, bookmarks.c.user_id == user_id
                )
            )
            & visible
        )
    elif view == "forked":
        condition = condition & agents.c.source_id.is_not(None)
    elif view == "drafts":
        condition = condition & (p["lifecycle"].astext == "draft")
    elif view == "recent":
        condition = condition & exists(
            select(usage).where(usage.c.agent_id == agents.c.id, usage.c.user_id == user_id)
        )
    elif view == "team":
        condition = condition & exists(
            select(memberships).where(memberships.c.agent_id == agents.c.id)
        )
    if q:
        condition = condition & or_(
            p["name"].astext.ilike(f"%{q}%"),
            p["tags"].astext.ilike(f"%{q}%"),
            p["model_settings"]["model"].astext.ilike(f"%{q}%"),
            p["tools"].astext.ilike(f"%{q}%"),
            p["category"].astext.ilike(f"%{q}%"),
        )
    for key, value in [("category", category), ("tools", tool)]:
        if value:
            condition = condition & p[key].astext.ilike(f"%{value}%")
    if model:
        condition = condition & p["model_settings"]["model"].astext.ilike(f"%{model}%")
    score = (
        select(func.avg(ratings.c.value)).where(ratings.c.agent_id == agents.c.id).scalar_subquery()
    )
    counts = (
        lambda table: select(func.count())
        .select_from(table)
        .where(table.c.agent_id == agents.c.id)
        .scalar_subquery()
    )
    orders = {
        "name": p["name"].astext.asc(),
        "newest": agents.c.created_at.desc(),
        "rating": score.desc().nulls_last(),
        "bookmarks": counts(bookmarks).desc(),
        "usage": counts(usage).desc(),
        "forks": agents.c.created_at.desc(),
    }
    fork = agents.alias("fork")
    orders["forks"] = (
        select(func.count())
        .select_from(fork)
        .where(fork.c.source_id == agents.c.id)
        .scalar_subquery()
        .desc()
    )
    if view == "recent":
        order = (
            select(func.max(usage.c.created_at))
            .where(usage.c.agent_id == agents.c.id, usage.c.user_id == user_id)
            .scalar_subquery()
            .desc()
        )
    else:
        order = orders.get(sort, agents.c.updated_at.desc())
    async with engine.connect() as conn:
        total = (
            await conn.execute(select(func.count()).select_from(agents).where(condition))
        ).scalar()
        rows = (
            (
                await conn.execute(
                    select(agents)
                    .where(condition)
                    .order_by(order, agents.c.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )
        return {
            "items": [await describe(conn, dict(row), user_id) for row in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


async def fork_profile(engine, user_id, agent_id):
    async with engine.connect() as conn:
        row, profile = await resolve_profile(conn, uuid.UUID(user_id), agent_id)
    profile.handle = profile.handle[:38] + "-" + uuid.uuid4().hex[:8]
    profile.name = profile.name[:90] + " (copy)"
    profile.visibility = "private"
    return await save_profile(engine, user_id, profile, source=row)


async def delete_profile(engine, user_id, agent_id):
    async with engine.begin() as conn:
        _, profile = await resolve_profile(conn, user_id, agent_id, owned=True)
        if profile.lifecycle != "archived":
            fail("Archive this Agent before deleting it.", 409)
        referenced = (
            await conn.execute(select(memberships).where(memberships.c.agent_id == agent_id))
        ).first()
        used = (
            await conn.execute(select(usage.c.id).where(usage.c.agent_id == agent_id).limit(1))
        ).first()
        forked = (
            await conn.execute(select(agents.c.id).where(agents.c.source_id == agent_id).limit(1))
        ).first()
        if referenced or used or forked:
            fail("This Agent is referenced by a Team, graph, or execution. Keep it archived.", 409)
        await conn.execute(delete(agents).where(agents.c.id == agent_id))


async def social(engine, user_id, agent_id, *, bookmark=None, rating=None, verified=None):
    async with engine.begin() as conn:
        await resolve_profile(conn, user_id, agent_id)
        if verified is not None:
            admin = (await conn.execute(select(User.is_admin).where(User.id == user_id))).scalar()
            if not admin:
                fail("Only admins may verify Agents.", 403)
            await conn.execute(
                update(agents).where(agents.c.id == agent_id).values(verified=verified)
            )
        elif rating is not None:
            await conn.execute(
                pg_insert(ratings)
                .values(agent_id=agent_id, user_id=user_id, value=rating)
                .on_conflict_do_update(
                    index_elements=["agent_id", "user_id"],
                    set_={"value": rating, "updated_at": func.now()},
                )
            )
        elif bookmark:
            await conn.execute(
                pg_insert(bookmarks)
                .values(agent_id=agent_id, user_id=user_id)
                .on_conflict_do_nothing()
            )
        else:
            await conn.execute(
                delete(bookmarks).where(
                    bookmarks.c.agent_id == agent_id, bookmarks.c.user_id == user_id
                )
            )


async def restore_version(engine, user_id, agent_id, version):
    async with engine.connect() as conn:
        await resolve_profile(conn, user_id, agent_id, owned=True)
        payload = (
            await conn.execute(
                select(versions.c.profile).where(
                    versions.c.agent_id == agent_id, versions.c.version == version
                )
            )
        ).scalar()
        if not payload:
            fail("Version not found.", 404)
    return await save_profile(engine, user_id, AgentWrite.model_validate(payload), agent_id)
