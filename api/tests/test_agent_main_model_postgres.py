"""Main-model synthesis through the real provider tool loop, using an isolated database."""

import json

import pytest
from sqlalchemy import select, update

from database.pg.agent_ops.tables import usage
from database.pg.models import GenerationHistory, Node
from services import inference_requests, openrouter
from services.agents import library
from services.agents import teams as team_service
from schemas.agents import TeamWrite
from services.agents.runtime import current_policy
from test_agents import profile
from test_agents_postgres import anyio_backend, configure_execution, db


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["direct", "unused_pool", "single", "parallel", "sequential", "auto_tools"])
async def test_independent_main_model_receives_results_and_writes_final_reply(db, monkeypatch, mode):
    execution, _, children, selected_team, websocket = await configure_execution(db, monkeypatch, with_team=False)
    ids = [str(c["id"]) for c in children]
    await team_service.save_team(db[0], db[1][0], TeamWrite(name="Pool", members=ids if mode != "direct" else []), selected_team["id"])
    async with db[0].begin() as conn:
        await conn.execute(update(Node).where(Node.id == "node").values(data={
            "model": "test/main", "teamId": str(selected_team["id"]), "selectedTools": [], "reply": "previous reply"}))
    for child in children:
        await library.save_profile(db[0], db[1][0], profile(
            handle=child["handle"], name=child["profile"]["name"],
            prompt_stack=[{"name": "Role", "text": "SUBAGENT_PRIVATE_INSTRUCTIONS"}],
            tools=child["profile"]["tools"],
            model_settings={"model": "test/worker", "temperature": 0.2}), child["id"])
    execution.available_models = [{"id": "test/main", "name": "Main model", "toolsSupport": True}]
    execution.request.model = "untrusted/client-model"
    execution.http_client = object()
    if mode == "auto_tools":
        from models.message import ToolEnum
        from services import stream
        from services.agents import main_tools
        from unittest.mock import AsyncMock
        async with db[0].begin() as conn:
            await conn.execute(update(Node).where(Node.id == "node").values(data={
                "model": "test/main", "teamId": str(selected_team["id"]),
                "selectedTools": ["execute_code"], "autoSelectTools": True, "reply": ""}))
        monkeypatch.setattr(stream, "_resolve_auto_selected_tools", AsyncMock(
            return_value=[ToolEnum.LINK_EXTRACTION]))
        monkeypatch.setattr(main_tools, "get_user_settings", AsyncMock(return_value=object()))
        monkeypatch.setattr(stream, "_get_auto_tool_candidates", lambda *args: [ToolEnum.LINK_EXTRACTION])
    rounds = []
    completed = []

    def build(**kwargs):
        kwargs.pop("credentials")
        kwargs.pop("available_models")
        return openrouter.OpenRouterReqChat(api_key="test-key", **kwargs)

    async def stream_data(client, url, headers, payload, **kwargs):
        policy = current_policy.get()
        names = {tool["function"]["name"] for tool in payload.get("tools", [])}
        if policy.agent_id is not None:
            assert payload["model"] == "test/worker"
            assert "delegate_agents" not in names
            assert "fetch_page_content" not in names
            assert payload["temperature"] == 0.2
            if policy.agent_id == ids[0]:
                assert "execute_code" in names
            else:
                assert "execute_code" not in names
            assert "SUBAGENT_PRIVATE_INSTRUCTIONS" in payload["messages"][0]["content"]
            completed.append(policy.agent_id)
            content = "Worker finding: " + policy.agent_id
        else:
            assert payload["model"] == "test/main"
            assert payload["temperature"] == execution.config.temperature
            assert ("fetch_page_content" in names) == (mode == "auto_tools")
            assert "execute_code" not in names
            assert "SUBAGENT_PRIVATE_INSTRUCTIONS" not in json.dumps(payload["messages"])
            assert ("delegate_agents" in names) == (mode != "direct")
            outputs = [json.loads(m["content"])["runs"] for m in payload["messages"]
                       if m.get("name") == "delegate_agents"]
            rounds.append(len(outputs))
            required = 0 if mode in {"direct", "unused_pool"} else 2 if mode == "sequential" else 1
            if len(outputs) < required:
                targets = ids if mode == "parallel" else [ids[len(outputs)]]
                instructions = "Find evidence" if not outputs else "Build on " + outputs[0][0]["result"]
                yield json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0,
                    "id": "delegate-" + str(len(outputs)), "type": "function", "function": {
                        "name": "delegate_agents", "arguments": json.dumps({"calls": [
                            {"agent_id": agent_id, "instructions": instructions} for agent_id in targets]})}}]},
                    "finish_reason": "tool_calls"}]})
                return
            if outputs:
                assert all(run["status"] == "completed" and run["result"].startswith("Worker finding:")
                           for batch in outputs for run in batch)
            content = "My final explanation based on the findings." if outputs else "Direct main-model answer."
        yield json.dumps({"choices": [{"delta": {"content": content}, "finish_reason": None}]})
        yield json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        yield "[DONE]"

    monkeypatch.setattr(inference_requests, "build_inference_request", build)
    monkeypatch.setattr(openrouter, "stream_openrouter_data", stream_data)
    await execution.execute()
    async with db[0].connect() as conn:
        data = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
        usage_count = len((await conn.execute(select(usage))).all())
    expected = "Direct main-model answer." if mode in {"direct", "unused_pool"} else "My final explanation based on the findings."
    assert data["reply"] == expected
    assert data["model"] == "test/main"
    if mode == "auto_tools":
        async with db[0].connect() as conn:
            actual_tools = (await conn.execute(select(GenerationHistory.selected_tools))).scalar_one()
        assert actual_tools == ["link_extraction"]
    assert usage_count == len(completed)
    main = next(run for run in execution.state["runs"].values() if run["parent_id"] is None)
    assert main["agent_id"] is None and main["version"] is None
    assert main["status"] == "completed"
    public_chunks = [call.args[0]["payload"] for call in websocket.send_json.call_args_list
                     if call.args[0]["type"] == "stream_chunk"]
    assert "".join(public_chunks) == expected
    assert rounds == {"direct": [0], "unused_pool": [0], "single": [0, 1], "parallel": [0, 1], "sequential": [0, 1, 2], "auto_tools": [0, 1]}[mode]


@pytest.mark.anyio
async def test_team_mention_selects_only_that_teams_pool(db, monkeypatch):
    execution, selected, children, team, _ = await configure_execution(db, monkeypatch)
    resolved = await team_service.resolve_mention(db[0], db[1][0], "@pool help")
    assert resolved == {"team_id": str(team["id"]), "message": "help"}
    await execution.authorize()
    assert execution.team_id == resolved["team_id"]
    assert {member["id"] for member in execution.pool} == {str(c["id"]) for c in children}
    assert str(selected["id"]) not in {member["id"] for member in execution.pool}
    assert execution.state["runs"] == {}



@pytest.mark.anyio
async def test_one_time_agent_node_conversion_preserves_replies_and_optional_selection(db, monkeypatch):
    from database.pg.models import Settings, GenerationHistory
    from services.agents.node_cutover import convert_agent_nodes, independent_model_data
    from sqlalchemy import insert
    import uuid
    execution, selected, _, team, _ = await configure_execution(db, monkeypatch)
    data = {"primaryAgentId": str(selected["id"]), "teamId": str(team["id"]),
            "reply": "Preserve answer", "agentExecution": {"id": "historical-execution"}}
    async with db[0].begin() as conn:
        await conn.execute(insert(Settings).values(user_id=db[1][0], settings_data={
            "models": {"defaultModel": "test/main"}}))
        await conn.execute(update(Node).where(Node.id == "node").values(data=data))
        await conn.execute(insert(GenerationHistory).values(id=uuid.uuid4(), user_id=db[1][0],
            graph_id=db[2], node_id="node", node_type="agent", model="test/old-worker",
            snapshot=data, preview="Preserve answer", selected_tools=[]))
        assert await convert_agent_nodes(conn) == (1, 1)
        assert await convert_agent_nodes(conn) == (0, 0)
        converted = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
        history = (await conn.execute(select(GenerationHistory.snapshot, GenerationHistory.model))).one()
    assert converted["model"] == "test/main"
    assert "agentIds" not in converted
    assert converted["teamId"] == str(team["id"])
    assert converted["selectedTools"] == []
    assert "primaryAgentId" not in converted
    assert converted["reply"] == data["reply"]
    assert converted["agentExecution"] == data["agentExecution"]
    assert history.snapshot == converted
    assert history.model == "test/old-worker"
    assert independent_model_data(converted, "another-default") == converted
