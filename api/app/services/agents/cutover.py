"""Explicit offline cutover. Kept out of application startup and production contracts."""

import copy
import json

from database.pg.agent_ops.team_crud import ensure_default_team
from database.pg.models import GenerationHistory, Node, Settings
from services.agents.node_cutover import convert_agent_nodes, independent_model_data
from sqlalchemy import select, text, update

LEGACY_TYPE = "routing"


def clean_reply(data):
    source = data if isinstance(data, dict) else {}
    return {
        "model": "",
        "selectedTools": [],
        "teamId": None,
        "reply": source.get("reply", ""),
        **(
            {"activeGenerationHistoryId": source["activeGenerationHistoryId"]}
            if source.get("activeGenerationHistoryId")
            else {}
        ),
    }


def clean_settings(value, default_model="", default_team_id=None):
    if isinstance(value, dict) and isinstance(value.get("models"), dict):
        default_model = value["models"].get("defaultModel", default_model)
    if isinstance(value, list):
        return [clean_settings(item, default_model, default_team_id) for item in value]
    if not isinstance(value, dict):
        return value
    result = {
        key: clean_settings(item, default_model, default_team_id)
        for key, item in value.items()
        if key not in {"blockRouting", "routingModel", "routing_model"}
    }
    if value.get("defaultNodeType") == LEGACY_TYPE:
        result["defaultNodeType"] = "agent"
    if "mainBloc" in value:
        if value["mainBloc"] == LEGACY_TYPE:
            result["mainBloc"] = "agent"
        result["options"] = [
            "agent" if item == LEGACY_TYPE else item for item in value.get("options", [])
        ]
    if value.get("type") == LEGACY_TYPE:
        result["type"] = "agent"
        result["data"] = {
            "model": "",
            "selectedTools": [],
            "teamId": str(default_team_id) if default_team_id else None,
        }
    elif value.get("type") == "agent" and "data" in value:
        result["data"] = independent_model_data(result["data"], default_model, default_team_id)
    return result


async def cutover(engine, neo4j, redis, *, maintenance_confirmed=False):
    if not maintenance_confirmed:
        raise ValueError(
            "Stop all API/UI workers and schedulers, back up all stores, then pass "
            "--maintenance-confirmed. Mixed versions are unsupported."
        )
    # All stores and the additive schema must be ready before the first mutation.
    await neo4j.verify_connectivity()
    await redis.client.ping()
    async with engine.connect() as conn:
        revision = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        if revision != "c7b9e12d6a30":
            raise ValueError("Apply the Agent additive migration before running cutover.")
        await conn.execute(text("SELECT 1 FROM agent_profiles LIMIT 1"))
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(751960281)"))
        rows = (
            await conn.execute(
                select(Node.graph_id, Node.id, Node.data).where(Node.type == LEGACY_TYPE)
            )
        ).all()
        for row in rows:
            await conn.execute(
                update(Node)
                .where(Node.graph_id == row.graph_id, Node.id == row.id)
                .values(type="agent", data=clean_reply(row.data))
            )
        histories = (
            await conn.execute(
                select(GenerationHistory.id, GenerationHistory.snapshot).where(
                    GenerationHistory.node_type == LEGACY_TYPE
                )
            )
        ).all()
        for row in histories:
            await conn.execute(
                update(GenerationHistory)
                .where(GenerationHistory.id == row.id)
                .values(
                    node_type="agent",
                    model=None,
                    selected_tools=[],
                    snapshot=clean_reply(row.snapshot),
                )
            )
        agent_nodes, agent_histories = await convert_agent_nodes(conn)
        settings = (
            await conn.execute(select(Settings.id, Settings.user_id, Settings.settings_data))
        ).all()
        for row in settings:
            default_team_id = await ensure_default_team(conn, row.user_id)
            cleaned = clean_settings(
                copy.deepcopy(row.settings_data), default_team_id=default_team_id
            )
            if cleaned != row.settings_data:
                await conn.execute(
                    update(Settings).where(Settings.id == row.id).values(settings_data=cleaned)
                )
    # Rerunning completes an interrupted cross-store cutover. Requires maintenance throughout.
    async with neo4j.session() as session:
        result = await session.run(
            "MATCH (n:GNode) WHERE n.type = $old SET n.type = 'agent' "
            "RETURN count(n) AS converted",
            old=LEGACY_TYPE,
        )
        await result.consume()
    invalidated = 0
    async for key in redis.client.scan_iter(match="pending_tool_continuation:*"):
        raw = await redis.client.get(key)
        if not raw:
            continue
        snapshot = json.loads(raw)
        if snapshot.get("node_type") == LEGACY_TYPE or (
            snapshot.get("node_type") == "agent"
            and (snapshot.get("agent_execution") or {}).get("orchestration_version") != 3
        ):
            await redis.client.delete(key)
            public_id = str(key).split(":", 1)[1]
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE tool_calls SET status = 'error', "
                        "result = CAST(:result AS jsonb) WHERE id::text = :id AND status = "
                        "'pending_user_input'"
                    ).bindparams(
                        result=json.dumps(
                            {"error": "Agent cutover invalidated this continuation."}
                        ),
                        id=public_id,
                    )
                )
            invalidated += 1
    async with engine.connect() as conn:
        if (await conn.execute(select(Node.id).where(Node.type == LEGACY_TYPE).limit(1))).first():
            raise RuntimeError("Cutover verification failed: legacy PostgreSQL nodes remain.")
    async with neo4j.session() as session:
        check = await session.run(
            "MATCH (n:GNode) WHERE n.type = $old RETURN count(n) AS count", old=LEGACY_TYPE
        )
        if (await check.single())["count"]:
            raise RuntimeError("Cutover verification failed: legacy Neo4j nodes remain.")
    return {
        "nodes": agent_nodes,
        "histories": agent_histories,
        "continuations": invalidated,
    }
