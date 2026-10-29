"""One-time conversion to an independent main model and one authorized Team."""

from database.pg.agent_ops.tables import teams
from database.pg.agent_ops.team_crud import ensure_default_team
from database.pg.models import GenerationHistory, Graph, Node, Settings, User
from sqlalchemy import select, update


def independent_model_data(data, default_model="", default_team_id=None):
    if not isinstance(data, dict):
        return data
    result = dict(data)
    if "primaryAgentId" in result:
        result.pop("primaryAgentId")
        result.update(model=default_model, selectedTools=[])
    result.pop("agentIds", None)
    if not result.get("teamId") and default_team_id:
        result["teamId"] = str(default_team_id)
    return result


async def convert_agent_nodes(conn):
    defaults = {
        row.user_id: (row.settings_data or {}).get("models", {}).get("defaultModel", "")
        for row in (await conn.execute(select(Settings.user_id, Settings.settings_data))).all()
    }
    user_ids = (await conn.execute(select(User.id))).scalars().all()
    default_teams = {user_id: await ensure_default_team(conn, user_id) for user_id in user_ids}
    ownership = {
        str(row.id): row.owner_id
        for row in (await conn.execute(select(teams.c.id, teams.c.owner_id))).all()
    }

    def converted(data, owner):
        result = independent_model_data(data, defaults.get(owner, ""), default_teams[owner])
        if ownership.get(str(result.get("teamId"))) != owner:
            result["teamId"] = str(default_teams[owner])
        return result

    rows = (
        await conn.execute(
            select(Node.graph_id, Node.id, Node.data, Graph.user_id)
            .join(Graph, Node.graph_id == Graph.id)
            .where(Node.type == "agent")
        )
    ).all()
    node_count = 0
    for row in rows:
        data = converted(row.data, row.user_id)
        if data != row.data:
            await conn.execute(
                update(Node)
                .where(Node.graph_id == row.graph_id, Node.id == row.id)
                .values(data=data)
            )
            node_count += 1
    histories = (
        await conn.execute(
            select(
                GenerationHistory.id, GenerationHistory.snapshot, GenerationHistory.user_id
            ).where(GenerationHistory.node_type == "agent")
        )
    ).all()
    history_count = 0
    for row in histories:
        data = converted(row.snapshot, row.user_id)
        if data != row.snapshot:
            await conn.execute(
                update(GenerationHistory)
                .where(GenerationHistory.id == row.id)
                .values(snapshot=data)
            )
            history_count += 1
    return node_count, history_count
