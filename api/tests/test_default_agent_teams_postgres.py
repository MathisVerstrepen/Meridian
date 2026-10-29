"""Default Team provisioning, exclusive node pools and Team mentions."""

import asyncio
import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import delete, insert, select, text, update

from database.pg.agent_ops.tables import agents, memberships, teams
from database.pg.agent_ops.team_crud import ensure_default_team
from database.pg.models import Node, Settings, User, create_initial_users
from database.pg.user_ops.user_crud import create_user_from_provider, create_user_with_password, ProviderUserPayload
from models.auth import ProviderEnum
from schemas.agents import TeamWrite
from services.agents import library, teams as team_service
from services.agents.node_cutover import convert_agent_nodes
from services.auth import UserPass
from test_agents import profile
from test_agents_postgres import anyio_backend, configure_execution, db


@pytest.mark.anyio
async def test_default_team_is_unique_under_concurrent_first_use(db):
    engine, (owner, other, _), _ = db
    results = await asyncio.gather(*(team_service.list_teams(engine, owner) for _ in range(8)))
    assert len({str(rows[0]["id"]) for rows in results}) == 1
    assert all(rows[0]["handle"] == "default" and rows[0]["is_default"] for rows in results)
    other_team = (await team_service.list_teams(engine, other))[0]
    assert other_team["id"] != results[0][0]["id"]


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["password", "provider", "initial"])
async def test_account_creation_provisions_default_team_in_same_transaction(db, kind):
    engine = db[0]
    handle = "new-" + uuid.uuid4().hex[:10]
    if kind == "password":
        user = await create_user_with_password(engine, handle, handle + "@example.test", "hashed")
    elif kind == "provider":
        user = await create_user_from_provider(engine, ProviderUserPayload(oauthId=handle, name=handle), ProviderEnum.GITHUB)
    else:
        user = (await create_initial_users(engine, [UserPass(username=handle, password="hashed")]))[0]
    async with engine.connect() as conn:
        row = (await conn.execute(select(teams).where(teams.c.owner_id == user.id))).mappings().one()
    assert row["is_default"] and row["handle"] == "default"


@pytest.mark.anyio
async def test_new_profiles_forks_and_drafts_join_default_but_edits_do_not_readd_removed_members(db):
    engine, (owner, other, _), _ = db
    created = await asyncio.gather(*(library.save_profile(engine, owner, profile(handle=f"new-{index}", lifecycle="draft")) for index in range(5)))
    default = (await team_service.list_teams(engine, owner))[0]
    assert set(default["members"]) == {row["id"] for row in created}
    async with engine.connect() as conn:
        positions = (await conn.execute(select(memberships.c.position).where(memberships.c.team_id == default["id"]))).scalars().all()
    assert sorted(positions) == list(range(5))
    await team_service.save_team(engine, owner, TeamWrite(name=default["name"], members=default["members"][1:]), default["id"])
    removed = next(row for row in created if row["id"] == default["members"][0])
    await library.save_profile(engine, owner, profile(handle=removed["handle"]), removed["id"])
    assert removed["id"] not in (await team_service.list_teams(engine, owner))[0]["members"]
    source = await library.save_profile(engine, other, profile(handle="public", visibility="public"))
    fork = await library.fork_profile(engine, str(owner), source["id"])
    assert fork["id"] in (await team_service.list_teams(engine, owner))[0]["members"]


@pytest.mark.anyio
async def test_node_configuration_assigns_default_and_rejects_individuals_and_foreign_teams(db, monkeypatch):
    execution, primary, children, selected, _ = await configure_execution(db, monkeypatch)
    engine, (owner, other, _), _ = db
    node = SimpleNamespace(type="agent", data={"model": "test/model", "reply": "Keep reply"})
    async with engine.begin() as conn:
        await team_service.configure_agent_nodes(conn, owner, [node])
        default = await ensure_default_team(conn, owner)
    assert node.data["teamId"] == str(default) and node.data["reply"] == "Keep reply"
    await execution.authorize()
    assert {member["id"] for member in execution.pool} == {str(c["id"]) for c in children}
    assert str(primary["id"]) not in {member["id"] for member in execution.pool}
    foreign = (await team_service.list_teams(engine, other))[0]
    for data in [{"teamId": str(foreign["id"])}, {"teamId": str(selected["id"]), "agentIds": [str(primary["id"])]}]:
        async with engine.begin() as conn:
            with pytest.raises(HTTPException):
                await team_service.configure_agent_nodes(conn, owner, [SimpleNamespace(type="agent", data=data)])
    async with engine.begin() as conn:
        await conn.execute(update(Node).where(Node.id == "node").values(data={"model": "test/model", "teamId": None}))
    with pytest.raises(HTTPException) as error:
        await execution.authorize()
    assert "Choose a Team" in error.value.detail


@pytest.mark.anyio
async def test_mentions_resolve_teams_only_and_default_handle_cannot_be_replaced(db):
    engine, (owner, other, _), _ = db
    await library.save_profile(engine, owner, profile(handle="solo-agent"))
    default = (await team_service.list_teams(engine, owner))[0]
    assert await team_service.resolve_mention(engine, owner, "@default help") == {"team_id": str(default["id"]), "message": "help"}
    custom = await team_service.save_team(engine, owner, TeamWrite(name="Research Team", handle="research-team"))
    assert (await team_service.resolve_mention(engine, owner, "@research-team help"))["team_id"] == str(custom["id"])
    for message in ["@solo-agent help", "@missing help", "@research-team @default help"]:
        with pytest.raises(HTTPException):
            await team_service.resolve_mention(engine, owner, message)
    with pytest.raises(HTTPException):
        await team_service.resolve_mention(engine, other, "@research-team help")
    with pytest.raises(HTTPException):
        await team_service.save_team(engine, owner, TeamWrite(name="Rename", handle="renamed"), default["id"])


@pytest.mark.anyio
async def test_additive_migration_backfills_default_teams_and_members_without_touching_node_replies(db):
    engine, users, _ = db
    async with engine.begin() as conn:
        # Model the preceding released schema without touching application credentials.
        await conn.execute(text("ALTER TABLE agent_teams DROP CONSTRAINT agent_teams_owner_handle"))
        await conn.execute(text("DROP INDEX agent_teams_one_default_per_owner"))
        await conn.execute(text("ALTER TABLE agent_teams DROP COLUMN handle, DROP COLUMN is_default"))
        await conn.execute(text("INSERT INTO agent_teams (id, owner_id, name, description) VALUES (:id, :owner, 'Research Team', '')"),
                           {"id": uuid.uuid4(), "owner": users[0]})
        profile_id = uuid.uuid4()
        await conn.execute(insert(agents).values(id=profile_id, owner_id=users[0], handle="old", profile=profile().model_dump(mode="json")))
        def upgrade(sync_conn):
            path = Path(__file__).resolve().parents[1] / "migrations/versions/c7b9e12d6a30_default_agent_teams.py"
            spec = importlib.util.spec_from_file_location("team_revision", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(sync_conn)):
                module.upgrade()
        await conn.run_sync(upgrade)
        assert (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()["reply"] == "old answer"
        assert (await conn.execute(select(teams.c.handle).where(teams.c.is_default.is_(False)))).scalar_one() == "research-team"
        defaults = (await conn.execute(select(teams).where(teams.c.is_default.is_(True)))).mappings().all()
        assert len(defaults) == len(users)
        own = next(team for team in defaults if team["owner_id"] == users[0])
        assert (await conn.execute(select(memberships.c.agent_id).where(memberships.c.team_id == own["id"]))).scalars().all() == [profile_id]
        await convert_agent_nodes(conn)
        node = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
        assert node["teamId"] == str(own["id"]) and node["reply"] == "old answer"
