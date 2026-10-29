import copy
import sys
from pathlib import Path
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.agent_ops.tables import executions
from database.pg.models import Node
from database.pg.chat_ops import get_tool_call_by_id
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from services import inference_requests
from services.agents import continuation, library
from services.agents.runtime import current_policy
from services.openrouter import _process_tool_calls_and_continue
from test_agents import profile
from test_agents_postgres import anyio_backend, configure_execution, db


class MemoryRedis:
    def __init__(self):
        self.client = self
        self.values = {}
        self.pending = {}

    async def set(self, key, value, **kwargs):
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script, count, key, token):
        if self.values.get(key) == token:
            del self.values[key]

    async def set_pending_tool_continuation(self, public_id, value):
        self.pending[public_id] = copy.deepcopy(value)

    async def get_pending_tool_continuation(self, public_id):
        return copy.deepcopy(self.pending.get(public_id))

    async def delete_pending_tool_continuation(self, public_id):
        self.pending.pop(public_id, None)


@pytest.mark.anyio
@pytest.mark.parametrize("subagent,automatic", [(False, False), (True, False), (False, True)])
async def test_paused_runs_revalidate_permissions_then_resume_and_synthesize(db, monkeypatch, subagent, automatic):
    execution, primary, children, team, websocket = await configure_execution(db, monkeypatch,
                                                                           with_team=subagent)
    target = children[0] if subagent else primary
    owner = db[1][0]
    candidates = []
    selector = AsyncMock(return_value=["ask_user"])
    if automatic:
        from services import stream as stream_service
        from services.agents import main_tools
        from models.message import ToolEnum
        selector.return_value = [ToolEnum.ASK_USER]
        monkeypatch.setattr(stream_service, "_resolve_auto_selected_tools", selector)
        monkeypatch.setattr(main_tools, "get_user_settings", AsyncMock(return_value=object()))
        monkeypatch.setattr(stream_service, "_get_auto_tool_candidates", lambda *args: candidates)
        async with db[0].begin() as conn:
            data = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
            await conn.execute(update(Node).where(Node.id == "node").values(data={**data, "autoSelectTools": True}))
    async def set_tools(tools):
        if automatic:
            candidates[:] = [ToolEnum(tool) for tool in tools]
        elif subagent:
            await library.save_profile(db[0], owner, profile(handle=target["handle"], tools=tools), target["id"])
        else:
            async with db[0].begin() as conn:
                data = (await conn.execute(select(Node.data).where(Node.id == "node"))).scalar_one()
                await conn.execute(update(Node).where(Node.id == "node").values(data={**data, "selectedTools": tools}))
    await set_tools(["ask_user"])
    redis = MemoryRedis()
    execution.redis = redis
    def build(**kwargs):
        return SimpleNamespace(**{"model_id": None, "file_hashes": {}, "pdf_engine": "default",
            "sandbox_input_files": [], "sandbox_input_warnings": [], **kwargs})
    monkeypatch.setattr(inference_requests, "build_inference_request", build)
    monkeypatch.setattr(continuation, "get_effective_graph_config", AsyncMock(return_value=(
        GraphConfigUpdate(), "global", None)))

    async def stream(req, engine, redis, final):
        policy = current_policy.get()
        final["usage_data"] = {"total_tokens": 5}
        if policy.agent_id is None and subagent:
            if any(m.get("name") == "delegate_agents" for m in req.messages):
                yield "Primary synthesis of answered child"
                return
            name = "delegate_agents"
            arguments = {"calls": [{"agent_id": str(target["id"]), "instructions": "Ask for details"}]}
        elif any(m.get("name") == "ask_user" for m in req.messages):
            assert req.selected_tools == ["ask_user"]
            assert "Answer" in req.messages[-1]["content"]
            yield "Answered child" if subagent else "Answered primary"
            return
        else:
            name, arguments = "ask_user", {"questions": [{"id": "q", "question": "Which?", "input_type": "text"}]}
        result = await _process_tool_calls_and_continue([{ "index": 0, "id": uuid.uuid4().hex,
            "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}],
            req.messages, req, redis)
        for feedback in result.feedback_strings:
            yield feedback
        if result.pending_tool_call_id:
            final["pending_tool_call_id"] = result.pending_tool_call_id
    monkeypatch.setattr(inference_requests, "stream_inference_response", stream)
    await execution.execute()
    assert execution.state["status"] == "paused"
    public_id, snapshot = next(iter(redis.pending.items()))
    assert snapshot["agent_execution"]["agent_id"] == (str(target["id"]) if subagent else None)
    tool_call = await get_tool_call_by_id(db[0], tool_call_id=public_id, user_id=str(owner))
    resume = dict(websocket=websocket, engine=db[0], redis=redis, http_client=None,
        available_models=[{"id": "test/model", "toolsSupport": True}], user_id=str(owner),
        tool_call=tool_call, snapshot=snapshot, answer={"q": {"value": "Answer"}})
    await set_tools([])
    with pytest.raises(HTTPException) as error:
        await continuation.resume_agent(**resume)
    assert error.value.status_code == 403 and public_id in redis.pending
    await set_tools(["ask_user"])
    await continuation.resume_agent(**resume)
    async with db[0].connect() as conn:
        state = (await conn.execute(select(executions.c.state))).scalar_one()
    assert state["status"] == "completed"
    resumed = next(run for run in state["runs"].values() if run["agent_id"] == (str(target["id"]) if subagent else None))
    assert resumed["version"] == (4 if subagent else None)
    assert not redis.pending
    if automatic:
        assert selector.await_count == 1
    primary_run = next(run for run in state["runs"].values() if not run["parent_id"])
    assert primary_run["result"] == ("Primary synthesis of answered child" if subagent else "Answered primary")
