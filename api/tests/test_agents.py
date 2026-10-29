import asyncio
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.chatDTO import GenerateRequest
from models.message import NodeTypeEnum, ToolEnum
from schemas.agents import AgentImport, AgentWrite, DelegationLimits, RatingWrite, TeamWrite
from services.agents import library
from services.agents import teams as team_service
from services.agents.cutover import clean_reply, clean_settings, cutover
from services.agents.execution import AgentExecution, validate_delegation_model
from services.agents.presets import starter_presets
from services.agents.runtime import AgentPolicy, current_policy, delegate_handler, guard_handler
from services.agents.runtime import delegation_tool, permitted_tools


@pytest.fixture
def anyio_backend():
    return "asyncio"


def profile(**values):
    return AgentWrite.model_validate({"handle": "helper", "name": "Helper", "lifecycle": "active",
        "model_settings": {"model": "test/model"}, **values})


def test_profile_contract_rejects_untrusted_policy_and_invalid_identity():
    for extra in [{"author": "admin"}, {"verified": True}, {"handle": "bad handle"},
                  {"icon": "../../path"}, {"accentColor": "red"},
                  {"tools": ["delegation"]}, {"context_rules": {}}]:
        with pytest.raises(ValidationError):
            profile(**extra)
    with pytest.raises(ValidationError):
        profile(lifecycle="draft", visibility="public")
    for rating in [0, 6, True, "5"]:
        with pytest.raises(ValidationError):
            RatingWrite(value=rating)
    assert AgentImport(profile=profile()).schema_version == 1
    assert len(starter_presets()) == 8


def test_team_contract_has_no_model_and_rejects_duplicate_members():
    member = uuid.uuid4()
    with pytest.raises(ValidationError):
        TeamWrite(name="Pool", members=[member, member])
    with pytest.raises(ValidationError):
        TeamWrite(name="Pool", router_model="test/model")
    assert TeamWrite(name="Pool", members=[member]).members == [member]


def test_legacy_node_contract_is_removed():
    with pytest.raises(ValidationError):
        GenerateRequest(graph_id="g", node_id="n", stream_type="routing")
    assert NodeTypeEnum.AGENT.value == "agent"
    assert len(ToolEnum) == 6


def test_cutover_keeps_only_replies_and_history_identity():
    old = {"reply": "Keep this answer", "activeGenerationHistoryId": "history",
           "routeGroupId": "old", "selectedRouteId": "route", "selectedTools": ["execute_code"],
           "model": "old/model", "usageData": {"cost": 10}, "autoSelectTools": True}
    converted = clean_reply(old)
    assert converted == {"reply": "Keep this answer", "activeGenerationHistoryId": "history",
                          "model": "", "selectedTools": [], "teamId": None}
    assert clean_reply(converted) == converted
    settings = {"blockRouting": {"routeGroups": [old]}, "models": {"routingModel": "old"},
                "customPrompt": "routing",
                "general": {"defaultNodeType": "routing"}, "nodePresets": {"presets": [
                    {"nodes": [{"type": "routing", "data": old}]}]}}
    result = clean_settings(settings)
    assert "blockRouting" not in result
    assert result["models"] == {}
    assert result["customPrompt"] == "routing"
    assert result["general"]["defaultNodeType"] == "agent"
    assert result["nodePresets"]["presets"][0]["nodes"][0]["data"] == {
        "model": "", "selectedTools": [], "teamId": None}
    assert settings["blockRouting"]


@pytest.mark.anyio
async def test_cutover_requires_explicit_maintenance_before_touching_stores():
    neo4j, redis = AsyncMock(), AsyncMock()
    with pytest.raises(ValueError, match="Stop all"):
        await cutover(AsyncMock(), neo4j, redis)
    neo4j.verify_connectivity.assert_not_called()


@pytest.mark.anyio
async def test_tool_policy_is_independent_for_child_tasks_and_never_expands_permissions():
    handler = AsyncMock(return_value={"ok": True})
    guarded = guard_handler("execute_code", handler)
    token = current_policy.set(AgentPolicy("execution", "primary", "a", 1, []))
    try:
        with pytest.raises(PermissionError):
            await guarded({}, None)
        async def child():
            child_token = current_policy.set(AgentPolicy("execution", "child", "b", 2,
                                                        [ToolEnum.EXECUTE_CODE]))
            try:
                return await guarded({}, None)
            finally:
                current_policy.reset(child_token)
        assert await asyncio.create_task(child()) == {"ok": True}
        with pytest.raises(PermissionError):
            await guarded({}, None)
        with pytest.raises(PermissionError, match="main model"):
            await delegate_handler({"calls": []}, None)
        assert delegation_tool() == []
    finally:
        current_policy.reset(token)
    assert handler.await_count == 1
    assert permitted_tools([ToolEnum.WEB_SEARCH]) == []
    assert permitted_tools([ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION]) == [
        ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION]


def test_capability_validation_is_actionable():
    validate_delegation_model("test/model", [{"id": "test/model", "toolsSupport": True}])
    with pytest.raises(HTTPException) as error:
        validate_delegation_model("test/model", [{"id": "test/model", "toolsSupport": False}])
    assert "tool-capable" in error.value.detail


@pytest.mark.anyio
async def test_invalid_mentions_fail_before_any_database_access():
    engine = SimpleNamespace(connect=lambda: pytest.fail("Database was touched"))
    for text in ["@one @two task", "@one   @two", "@bad! task"]:
        with pytest.raises(HTTPException):
            await team_service.resolve_mention(engine, uuid.uuid4(), text)
    assert await team_service.resolve_mention(engine, uuid.uuid4(), "ordinary @text") == {
        "team_id": None, "message": "ordinary @text"}


@pytest.mark.anyio
async def test_scheduler_parallel_siblings_sequential_rounds_and_limits():
    ids = [str(uuid.uuid4()) for _ in range(3)]
    execution = AgentExecution(engine=None, websocket=AsyncMock(),
        request=GenerateRequest(graph_id=str(uuid.uuid4()), node_id="node", stream_type="agent"),
        user_id=str(uuid.uuid4()), graph_config=None, credentials=None, messages=[],
        http_client=None, redis_manager=None, available_models=[])
    execution.pool = [{"id": member} for member in ids]
    execution.authorize = AsyncMock()
    started, release = [], asyncio.Event()
    async def run(agent_id, instructions, parent_id):
        started.append(str(agent_id))
        if len(started) == 2:
            release.set()
        await release.wait()
        return {"id": str(uuid.uuid4()), "agent_id": str(agent_id), "result": instructions,
                "status": "failed" if str(agent_id) == ids[1] else "completed"}
    execution.run = run
    token = current_policy.set(AgentPolicy("execution", "primary", "a", 1, [], execution.delegate))
    try:
        first = await execution.delegate({"calls": [{"agent_id": member, "instructions": "task"}
                                                    for member in ids[:2]]}, None)
        assert len(started) == 2
        assert {result["status"] for result in first["runs"]} == {"completed", "failed"}
        assert len({result["id"] for result in first["runs"]}) == 2
        second = await execution.delegate({"calls": [{"agent_id": ids[2],
            "instructions": "Build on " + first["runs"][0]["result"]}]}, None)
        assert second["runs"][0]["result"] == "Build on task"
        assert execution.state["rounds"] == 2
        with pytest.raises(PermissionError, match="outside"):
            await execution.delegate({"calls": [{"agent_id": str(uuid.uuid4()), "instructions": "bad"}]}, None)
        execution.limits = DelegationLimits(rounds=2)
        with pytest.raises(ValueError, match="round limit"):
            await execution.delegate({"calls": [{"agent_id": ids[0], "instructions": "bad"}]}, None)
        execution.limits = DelegationLimits(total_calls=3)
        with pytest.raises(ValueError, match="total subagent"):
            await execution.delegate({"calls": [{"agent_id": ids[0], "instructions": "bad"}]}, None)
    finally:
        current_policy.reset(token)


@pytest.mark.anyio
async def test_native_parallel_delegation_calls_share_a_round_and_keep_call_results(monkeypatch):
    from services.openrouter import _process_tool_calls_and_continue
    from services.tools import TOOL_HANDLERS_BY_NAME

    calls = [{"agent_id": str(uuid.uuid4()), "instructions": f"Task {i}"} for i in range(3)]
    handler = AsyncMock(return_value={"runs": [{"id": str(i), "result": f"Result {i}"}
                                             for i in range(3)]})
    monkeypatch.setitem(TOOL_HANDLERS_BY_NAME, "delegate_agents", handler)
    req = SimpleNamespace(graph_id=None, node_id=None, user_id=None, messages=[])
    native = [{"index": index, "id": f"call-{index}", "type": "function", "function": {
        "name": "delegate_agents", "arguments": json.dumps({"calls": batch})}}
        for index, batch in enumerate([calls[:2], calls[2:]])]
    result = await _process_tool_calls_and_continue(native, [], req, AsyncMock())
    handler.assert_awaited_once_with({"calls": calls}, req)
    outputs = [json.loads(message["content"]) for message in result.messages
               if message["role"] == "tool"]
    assert [len(output["runs"]) for output in outputs] == [2, 1]


def test_agent_settings_cutover_keeps_parallel_presets_and_converts_old_profile_selection():
    settings = {"models": {"defaultModel": "test/main"}, "nodePresets": {"presets": [{"nodes": [
        {"type": "parallelization", "data": {"models": [{"model": "test/worker"}]}},
        {"type": "agent", "data": {"primaryAgentId": "profile-id", "teamId": "team-id"}},
    ]}]}}
    converted = clean_settings(settings)
    assert converted["nodePresets"]["presets"][0]["nodes"] == [
        {"type": "parallelization", "data": {"models": [{"model": "test/worker"}]}},
        {"type": "agent", "data": {"model": "test/main", "selectedTools": [], "teamId": "team-id"}},
    ]
    assert clean_settings(converted) == converted
