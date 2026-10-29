import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from neo4j import AsyncGraphDatabase
from sqlalchemy import insert, select, text, update

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.agent_ops.tables import AGENT_TABLES
from database.pg.models import GenerationHistory, Node, Settings, ToolCall
from database.redis.redis_ops import RedisManager
from services.agents.cutover import cutover
from test_agents_postgres import anyio_backend, db


@pytest.mark.anyio
async def test_additive_revision_and_coordinated_cross_store_cutover(db):
    neo_url = os.getenv("AGENT_TEST_NEO4J_URL")
    redis_port = os.getenv("AGENT_TEST_REDIS_PORT")
    if not neo_url or not redis_port:
        pytest.skip("Set isolated AGENT_TEST_NEO4J_URL and AGENT_TEST_REDIS_PORT for cutover validation")
    engine, users, graph = db
    node_data = {"reply": "Current answer", "routeGroupId": "old-group", "model": "old-model",
                 "selectedTools": ["execute_code"], "usageData": {"cost": 20}}
    history_id, tool_id = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(update(Node).where(Node.id == "node").values(type="routing", data=node_data))
        await conn.execute(insert(GenerationHistory).values(id=history_id, user_id=users[0],
            graph_id=graph, node_id="node", node_type="routing", model="old-model",
            selected_tools=["execute_code"], preview="Historical answer",
            snapshot={**node_data, "reply": "Historical answer"}))
        await conn.execute(insert(Settings).values(user_id=users[0], settings_data={
            "blockRouting": {"routeGroups": [{"name": "Never migrate this"}]},
            "models": {"routingModel": "old-model"}, "general": {"defaultNodeType": "routing"}}))
        await conn.execute(insert(ToolCall).values(id=tool_id, user_id=users[0], graph_id=graph,
            node_id="node", tool_name="ask_user", status="pending_user_input", arguments={},
            result={}, model_context_payload="{}"))
        # Run the actual revision against the previous schema, checking it is additive.
        def upgrade(sync_conn):
            for table in reversed(AGENT_TABLES):
                table.drop(sync_conn)
            path = Path(__file__).resolve().parents[1] / "migrations/versions/a8e6f2c9d401_add_agent_profiles_and_teams.py"
            spec = importlib.util.spec_from_file_location("agent_revision", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(sync_conn)):
                module.upgrade()
            path = path.parent / "c7b9e12d6a30_default_agent_teams.py"
            spec = importlib.util.spec_from_file_location("team_revision", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(sync_conn)):
                module.upgrade()
        await conn.run_sync(upgrade)
        assert (await conn.execute(select(Node.type).where(Node.id == "node"))).scalar_one() == "routing"
        await conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)"))
        await conn.execute(text("INSERT INTO alembic_version VALUES ('c7b9e12d6a30')"))
    neo = AsyncGraphDatabase.driver(neo_url, auth=None)
    redis = RedisManager("127.0.0.1", int(redis_port), None)
    try:
        async with neo.session() as session:
            await session.run("CREATE (n:GNode {unique_id: $id, type: 'routing'})", id=str(graph))
        await redis.set_pending_tool_continuation(str(tool_id), {
            "node_type": "routing", "graph_id": str(graph), "node_id": "node"})
        report = await cutover(engine, neo, redis, maintenance_confirmed=True)
        assert report["nodes"] >= 1 and report["histories"] >= 1 and report["continuations"] == 1
        async with engine.connect() as conn:
            node = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
            history = (await conn.execute(select(GenerationHistory.snapshot, GenerationHistory.model))).one()
            assert node == {"model": "", "selectedTools": [], "teamId": node["teamId"], "reply": "Current answer"}
            assert history.snapshot == {"model": "", "selectedTools": [], "teamId": node["teamId"], "reply": "Historical answer"}
            assert history.model is None
            settings = (await conn.execute(select(Settings.settings_data))).scalar_one()
            assert settings == {"general": {"defaultNodeType": "agent"}, "models": {}}
            assert (await conn.execute(select(ToolCall.status))).scalar_one() == "error"
        assert not await redis.get_pending_tool_continuation(str(tool_id))
        assert await cutover(engine, neo, redis, maintenance_confirmed=True) == {
            "nodes": 0, "histories": 0, "continuations": 0}
    finally:
        async with neo.session() as session:
            await session.run("MATCH (n:GNode {unique_id: $id}) DETACH DELETE n", id=str(graph))
        await neo.close()
        await redis.close()
