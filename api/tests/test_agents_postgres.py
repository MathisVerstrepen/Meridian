"""Run against a disposable database with AGENT_TEST_DATABASE_URL; never uses app credentials."""

import asyncio
import copy
import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.agent_ops.tables import agents, executions, memberships, ratings, teams, usage, versions
from database.pg.graph_ops.generation_history_crud import restore_generation_history
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from database.pg.models import GenerationHistory, Graph, Node, User
from models.chatDTO import GenerateRequest
from routers.agents import agent_user_id, router
from schemas.agents import TeamWrite
from services.agents import execution as execution_module
from services.agents import library
from services.agents import teams as team_service
from services.agents.execution import AgentExecution
from services.agents.runtime import current_policy, delegate_handler
from services import inference_requests
from test_agents import profile


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db():
    url = os.getenv("AGENT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("AGENT_TEST_DATABASE_URL must point to a disposable PostgreSQL database")
    admin = create_async_engine(url)
    schema = "agent_test_" + uuid.uuid4().hex
    async with admin.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema + ",public"}})
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    users = [uuid.uuid4() for _ in range(3)]
    graph = uuid.uuid4()
    async with engine.begin() as conn:
        for index, user_id in enumerate(users):
            await conn.execute(insert(User).values(id=user_id, username=f"user{index}", plan_type="free", is_admin=index == 2))
        await conn.execute(insert(Graph).values(id=graph, user_id=users[0], name="Agent tests"))
        await conn.execute(insert(Node).values(graph_id=graph, id="node", type="agent", position_x=0,
            position_y=0, data={"model": "", "selectedTools": [], "teamId": None, "reply": "old answer"}))
    try:
        yield engine, users, graph
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.mark.anyio
async def test_profile_lifecycle_versions_marketplace_and_team_ownership(db):
    engine, (owner, other, admin), _ = db
    first = await library.save_profile(engine, owner, profile(visibility="public"))
    agent_id = first["id"]
    assert first["author"] == "user0" and first["version"] == 1
    assert (await library.list_profiles(engine, other, view="marketplace", q="Helper"))["total"] == 1
    await library.social(engine, other, agent_id, bookmark=True)
    await library.social(engine, other, agent_id, rating=2)
    await library.social(engine, other, agent_id, rating=5)
    with pytest.raises(HTTPException) as error:
        await library.social(engine, other, agent_id, verified=True)
    assert error.value.status_code == 403
    await library.social(engine, admin, agent_id, verified=True)
    listing = (await library.list_profiles(engine, other, view="bookmarked"))["items"][0]
    assert listing["verified"] and listing["rating_average"] == 5 and listing["rating_count"] == 1
    fork = await library.fork_profile(engine, str(other), agent_id)
    assert fork["source_id"] == agent_id and fork["source_version"] == 1
    assert fork["profile"]["visibility"] == "private"
    await library.save_profile(engine, owner, profile(description="changed"), agent_id)
    restored = await library.restore_version(engine, owner, agent_id, 1)
    assert restored["version"] == 3 and not restored["verified"]
    assert restored["profile"]["description"] == ""
    with pytest.raises(HTTPException):
        await team_service.save_team(engine, other, TeamWrite(name="Wrong owner", members=[agent_id]))
    team = await team_service.save_team(engine, owner, TeamWrite(name="Pool", members=[agent_id]))
    with pytest.raises(HTTPException):
        await team_service.save_team(engine, other, TeamWrite(name="Stolen"), team["id"])
    archived = profile(lifecycle="archived")
    await library.save_profile(engine, owner, archived, agent_id)
    with pytest.raises(HTTPException):
        async with engine.connect() as conn:
            await library.resolve_profile(conn, owner, agent_id, execute=True)
    assert (await library.list_profiles(engine, other, view="marketplace"))["total"] == 0
    assert (await library.list_profiles(engine, other, view="bookmarked"))["total"] == 0
    with pytest.raises(HTTPException) as error:
        await library.delete_profile(engine, owner, agent_id)
    assert error.value.status_code == 409
    # A profile with no references may be archived and permanently deleted.
    disposable = await library.save_profile(engine, other, profile(handle="disposable", lifecycle="archived"))
    async with engine.begin() as conn:
        await conn.execute(delete(memberships).where(memberships.c.agent_id == disposable["id"]))
    await library.delete_profile(engine, other, disposable["id"])


@pytest.mark.anyio
async def test_authenticated_api_import_export_filters_mentions_and_fork_access(db):
    engine, (owner, other, _), _ = db
    app = FastAPI()
    app.state.pg_engine = engine
    app.include_router(router)
    app.dependency_overrides[agent_user_id] = lambda: owner
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = profile(tags=["Python"], tools=["execute_code"], category="Engineering").model_dump(mode="json")
        created = await client.post("/agents", json=payload)
        assert created.status_code == 200, created.text
        agent_id = created.json()["id"]
        assert (await client.post("/agents", json={**payload, "verified": True})).status_code == 422
        exported = (await client.get(f"/agents/{agent_id}/export")).json()
        exported["profile"]["handle"] = "imported"
        assert (await client.post("/agents/import", json=exported)).status_code == 200
        page = (await client.get("/agents?q=python&tool=execute_code&category=Engineering&limit=1")).json()
        assert page["total"] == 2 and len(page["items"]) == 1
        team = (await client.post("/agents/teams", json={"name": "Research", "handle": "research", "members": [agent_id]})).json()
        mention = await client.post("/agents/resolve-mention", json={"message": "@research explain"})
        assert mention.json() == {"team_id": team["id"], "message": "explain"}
        for message in ["@unknown test", "@helper @imported test"]:
            assert (await client.post("/agents/resolve-mention", json={"message": message})).status_code >= 400
        app.dependency_overrides[agent_user_id] = lambda: other
        assert (await client.get(f"/agents/{agent_id}")).status_code == 404
        assert (await client.post(f"/agents/{agent_id}/fork")).status_code == 404
        assert (await client.put(f"/agents/{agent_id}/rating", json={"value": 5})).status_code == 404


async def configure_execution(db, monkeypatch, *, with_team=True):
    engine, (owner, _, _), graph = db
    primary = await library.save_profile(engine, owner, profile())
    children = [await library.save_profile(engine, owner, profile(handle=f"child-{i}", name=f"Child {i}",
        tools=["execute_code"] if i == 0 else [])) for i in range(2)]
    team = await team_service.save_team(engine, owner, TeamWrite(name="Pool", members=[c["id"] for c in children] if with_team else []))
    async with engine.begin() as conn:
        await conn.execute(update(Node).where(Node.id == "node").values(data={
            "model": "test/model", "selectedTools": [], "teamId": str(team["id"]),
            "reply": "old answer"}))
    websocket = SimpleNamespace(send_json=AsyncMock())
    execution = AgentExecution(engine=engine, websocket=websocket,
        request=GenerateRequest(graph_id=str(graph), node_id="node", stream_type="agent"),
        user_id=str(owner), graph_config=GraphConfigUpdate(), credentials=None,
        messages=[{"role": "system", "content": "global"}, {"role": "user", "content": "question"}],
        http_client=None, redis_manager=None, available_models=[{"id": "test/model", "toolsSupport": True}])
    def build(**kwargs):
        return SimpleNamespace(**kwargs)
    monkeypatch.setattr(inference_requests, "build_inference_request", build)
    return execution, primary, children, team, websocket


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["direct", "single", "parallel", "sequential", "partial_failure"])
async def test_model_directed_execution_tree_usage_history_and_synthesis(db, monkeypatch, mode):
    engine, users, graph = db
    execution, primary, children, _, websocket = await configure_execution(db, monkeypatch,
        with_team=mode != "direct")
    concurrent = set()
    barrier = asyncio.Event()
    async def stream(req, engine, redis, final):
        policy = current_policy.get()
        final["usage_data"] = {"total_tokens": 10, "cost": 0.1}
        if policy.agent_id is None:
            assert req.selected_tools == []
            if mode != "direct":
                members = children if mode in {"parallel", "partial_failure"} else children[:1]
                first = await delegate_handler({"calls": [{"agent_id": str(child["id"]),
                    "instructions": "Research"} for child in members]}, req)
                if mode == "sequential":
                    second = await delegate_handler({"calls": [{"agent_id": str(children[1]["id"]),
                        "instructions": "Use " + first["runs"][0]["result"]}]}, req)
                    assert second["runs"][0]["result"] == "child result"
                if mode == "partial_failure":
                    assert {r["status"] for r in first["runs"]} == {"completed", "failed"}
            yield "Final synthesis"
        else:
            concurrent.add(policy.run_id)
            if len(concurrent) == 2:
                barrier.set()
            if mode in {"parallel", "partial_failure"}:
                await asyncio.wait_for(barrier.wait(), 5)
            if mode == "partial_failure" and policy.agent_id == str(children[1]["id"]):
                raise RuntimeError("Provider failure")
            yield "child result"
    monkeypatch.setattr(inference_requests, "stream_inference_response", stream)
    await execution.execute()
    expected = {"direct": 1, "single": 2, "parallel": 3, "sequential": 3, "partial_failure": 3}[mode]
    assert len(execution.state["runs"]) == expected
    assert len({r["id"] for r in execution.state["runs"].values()}) == expected
    events = [call.args[0] for call in websocket.send_json.call_args_list]
    assert all(e.get("run_id") for e in events if e["type"].startswith("agent_run"))
    assert not any(e["type"] == "routing_response" for e in events)
    async with engine.connect() as conn:
        data = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
        assert data["reply"] == "Final synthesis"
        assert "context_messages" not in data["agentExecution"]
        assert data["usageData"]["total_tokens"] >= 10
        history_id = (await conn.execute(select(GenerationHistory.id))).scalar_one()
        assert (await conn.execute(select(executions.c.state))).scalar_one()["status"] == "completed"
    await restore_generation_history(engine, graph_id=str(graph), node_id="node",
        history_id=str(history_id), user_id=str(users[0]))
    foreign = await team_service.save_team(engine, users[1], TeamWrite(name="Private"))
    async with engine.begin() as conn:
        await conn.execute(update(Node).where(Node.id == "node").values(data={**data, "teamId": str(foreign["id"])}))
    execution.state.pop("node_configuration", None)
    with pytest.raises(HTTPException):
        await execution.authorize()



@pytest.mark.anyio
async def test_authorization_is_rechecked_before_launch_and_resume(db, monkeypatch):
    execution, _, children, team, _ = await configure_execution(db, monkeypatch)
    await execution.authorize()
    async with db[0].begin() as conn:
        await conn.execute(delete(memberships).where(memberships.c.team_id == team["id"]))
    token = current_policy.set(SimpleNamespace(run_id="primary", paused=False))
    try:
        with pytest.raises(PermissionError):
            await execution.delegate({"calls": [{"agent_id": str(children[0]["id"]), "instructions": "bad"}]}, None)
    finally:
        current_policy.reset(token)


@pytest.mark.anyio
async def test_custom_svg_icons_survive_profile_versions_forks_and_json_import_export(db):
    from services.agents import catalog
    from schemas.agents import AgentImport
    from utils.svg_icon import normalize_svg_icon
    engine, (owner, other, _), _ = db
    svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="8"/></svg>'
    normalized = normalize_svg_icon(svg)
    created = await library.save_profile(engine, owner, profile(iconSvg=svg, visibility="public"))
    agent_id = created["id"]
    assert created["profile"]["iconSvg"] == normalized
    exported = await catalog.export_profile(engine, owner, agent_id)
    imported = AgentImport.model_validate_json(exported.model_dump_json())
    restored_copy = await library.save_profile(engine, other, imported.profile.model_copy(update={"handle": "icon-import", "visibility": "private"}))
    assert restored_copy["profile"]["iconSvg"] == normalized
    fork = await library.fork_profile(engine, str(other), agent_id)
    assert fork["profile"]["iconSvg"] == normalized
    await library.save_profile(engine, owner, profile(iconSvg=None, visibility="public"), agent_id)
    restored = await library.restore_version(engine, owner, agent_id, 1)
    assert restored["profile"]["iconSvg"] == normalized and restored["version"] == 3
    history = await catalog.list_versions(engine, owner, agent_id)
    assert len(history) == 3 and history[-1]["profile"]["iconSvg"] == normalized
