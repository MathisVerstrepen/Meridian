import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from test_agents_postgres import anyio_backend, configure_execution, db
from test_agents import profile
from database.pg.agent_ops.tables import executions
from services import inference_requests
from services.agents import library
from services.agents.runtime import current_policy, delegate_handler


@pytest.mark.anyio
async def test_server_model_overrides_retries_fallback_and_usage(db, monkeypatch):
    execution, _, children, _, _ = await configure_execution(db, monkeypatch)
    primary = children[0]
    configured = profile(handle=primary["handle"], model_settings={"model": "test/model", "fallback_model": "test/fallback",
        "retry_count": 1, "max_tokens": 65, "temperature": 0.3, "top_p": 0.8,
        "top_k": 12, "presence_penalty": 0.2, "frequency_penalty": -0.2,
        "repetition_penalty": 1.1, "reasoning_effort": "high", "exclude_reasoning": True})
    await library.save_profile(db[0], db[1][0], configured, primary["id"])
    execution.request.model = "untrusted/client-model"
    attempts = []
    async def stream(req, engine, redis, final):
        attempts.append(req.model)
        assert req.config.max_tokens == 65 and req.config.temperature == 0.3
        assert req.config.reasoning_effort == "high" and req.config.exclude_reasoning
        final["usage_data"] = {"total_tokens": 10, "cost": 0.1}
        if len(attempts) < 3:
            raise RuntimeError("Retryable failure before tool side effects")
        yield "Recovered"
    monkeypatch.setattr(inference_requests, "stream_inference_response", stream)
    await execution.authorize()
    run = await execution.run(primary["id"], "Research", "main-run")
    assert attempts == ["test/model", "test/model", "test/fallback"]
    run = next(iter(execution.state["runs"].values()))
    assert run["attempts"] == 3 and run["version"] == 2 and run["result"] == "Recovered"
    assert sum(item["total_tokens"] for item in run["usage"]) == 30


@pytest.mark.anyio
async def test_subagent_retries_are_independent_of_parent_delegation_calls(db, monkeypatch):
    execution, primary, children, _, _ = await configure_execution(db, monkeypatch)
    await library.save_profile(db[0], db[1][0], profile(handle=children[0]["handle"],
        model_settings={"model": "test/model", "retry_count": 1}), children[0]["id"])
    attempts = 0
    async def stream(req, engine, redis, final):
        nonlocal attempts
        if current_policy.get().agent_id is None:
            result = await delegate_handler({"calls": [{"agent_id": str(children[0]["id"]),
                                                         "instructions": "Task"}]}, req)
            assert result["runs"][0]["status"] == "completed"
            yield "Synthesis"
        else:
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Temporary provider failure")
            yield "Recovered child"
    monkeypatch.setattr(inference_requests, "stream_inference_response", stream)
    await execution.execute()
    assert attempts == 2


@pytest.mark.anyio
async def test_cancellation_propagates_to_parallel_children_with_attributable_partial_state(db, monkeypatch):
    execution, primary, children, _, _ = await configure_execution(db, monkeypatch)
    started = set()
    ready, blocked = asyncio.Event(), asyncio.Event()
    async def stream(req, engine, redis, final):
        policy = current_policy.get()
        if policy.agent_id is None:
            await delegate_handler({"calls": [{"agent_id": str(c["id"]), "instructions": "Task"}
                                                for c in children]}, req)
        else:
            started.add(policy.run_id)
            if len(started) == 2:
                ready.set()
            yield "Partial child result"
            await blocked.wait()
    monkeypatch.setattr(inference_requests, "stream_inference_response", stream)
    task = asyncio.create_task(execution.execute())
    await asyncio.wait_for(ready.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert {run["status"] for run in execution.state["runs"].values()} == {"cancelled"}
    assert len(execution.state["runs"]) == 3
    async with db[0].connect() as conn:
        state = (await conn.execute(select(executions.c.state))).scalar_one()
    assert state["status"] == "cancelled"
    assert len([run for run in state["runs"].values() if run["result"]]) == 2


@pytest.mark.anyio
async def test_overall_budget_finishes_once_with_an_actionable_attributed_error(db, monkeypatch):
    from schemas.agents import DelegationLimits
    execution, _, _, _, websocket = await configure_execution(db, monkeypatch, with_team=False)
    execution.limits = DelegationLimits(budget_seconds=1)
    async def stream(req, engine, redis, final):
        yield "Partial response"
        await asyncio.Event().wait()
    monkeypatch.setattr(inference_requests, "stream_inference_response", stream)
    await execution.execute()
    assert execution.state["status"] == "cancelled"
    events = [call.args[0] for call in websocket.send_json.call_args_list]
    errors = [event for event in events if event["type"] == "stream_error"]
    assert len(errors) == 1 and "budget exhausted" in errors[0]["payload"]["message"]
    assert not any(event["type"] == "stream_end" for event in events)
