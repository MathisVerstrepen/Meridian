"""Resume one attributed run, then synthesize completed sibling results in its primary."""

import asyncio
import copy
import json
import uuid
from datetime import datetime, timezone

from database.pg.agent_ops.tables import executions
from database.pg.chat_ops import update_tool_call_by_id
from database.pg.models import Node, ToolCallStatusEnum
from models.chatDTO import GenerateRequest
from models.message import NodeTypeEnum, ToolEnum
from models.tool_question import AskUserArguments
from services.agents.execution import AgentExecution
from services.agents.library import fail, resolve_profile
from services.agents.runtime import permitted_tools
from services.graph_service import get_effective_graph_config
from services.tools.ask_user import build_ask_user_answer_result, normalize_ask_user_answers
from sqlalchemy import select


async def resume_agent(
    *, websocket, engine, redis, http_client, available_models, user_id, tool_call, snapshot, answer
):
    metadata = snapshot.get("agent_execution") or {}
    if metadata.get("orchestration_version") != 3:
        fail("Agent execution behavior changed. Run the node again with a main model.", 409)
    if snapshot.get("user_id") != user_id or str(snapshot.get("graph_id")) != str(
        tool_call.graph_id
    ):
        fail("Continuation identity does not match this request.", 403)
    execution_id = uuid.UUID(metadata["execution_id"])
    lock = f"agent_resume:{execution_id}"
    lock_token = uuid.uuid4().hex
    if not await redis.client.set(lock, lock_token, nx=True, ex=1800):
        fail("Another Team member is resuming. Try again after it finishes.", 409)
    try:
        async with engine.connect() as conn:
            node_data = (
                await conn.execute(
                    select(Node.data).where(
                        Node.graph_id == tool_call.graph_id, Node.id == tool_call.node_id
                    )
                )
            ).scalar_one()
            if (node_data.get("agentExecution") or {}).get("id") != str(execution_id):
                fail(
                    "A newer execution replaced this question. Continue with the current run.", 409
                )
            row = (
                (
                    await conn.execute(
                        select(executions).where(
                            executions.c.id == execution_id,
                            executions.c.owner_id == uuid.UUID(user_id),
                            executions.c.graph_id == tool_call.graph_id,
                            executions.c.node_id == tool_call.node_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                fail("Agent execution no longer exists.", 404)
            state = copy.deepcopy(row["state"])
            if state.get("status") != "paused":
                fail("This Agent execution is no longer waiting for input.", 409)
            run = state["runs"].get(metadata.get("run_id"))
            if (
                not run
                or run["status"] != "paused"
                or run.get("pending_tool_call_id") != str(tool_call.id)
            ):
                fail("This Agent run is no longer waiting for this answer.", 409)
        request = GenerateRequest(
            graph_id=str(tool_call.graph_id),
            node_id=tool_call.node_id,
            stream_type=NodeTypeEnum.AGENT,
        )
        config, _, credentials = await get_effective_graph_config(engine, request.graph_id, user_id)
        execution = AgentExecution(
            engine=engine,
            websocket=websocket,
            request=request,
            user_id=user_id,
            graph_config=config,
            credentials=credentials,
            messages=state["context_messages"],
            http_client=http_client,
            redis_manager=redis,
            available_models=available_models,
            state=state,
        )
        await execution.authorize()
        if run["parent_id"]:
            async with engine.connect() as conn:
                _, profile = await resolve_profile(
                    conn, uuid.UUID(user_id), uuid.UUID(run["agent_id"]), execute=True
                )
            tools = profile.tools
        else:
            tools = await execution.main_tools()
        if ToolEnum.ASK_USER not in permitted_tools(tools):
            fail("Ask User permission was revoked. Restore permission or run the node again.", 403)
        if run["parent_id"] and run["agent_id"] not in {member["id"] for member in execution.pool}:
            fail("This subagent is no longer authorized by the configured Team.", 403)
        remaining = execution.limits.budget_seconds - state["elapsed_seconds"]
        if remaining <= 0:
            fail("The Agent execution budget has been exhausted. Run the node again.")
        arguments = AskUserArguments.model_validate(tool_call.arguments)
        answers = normalize_ask_user_answers(arguments, answer)
        result = build_ask_user_answer_result(
            arguments, answers, submitted_at=datetime.now(timezone.utc).isoformat()
        )
        payload = json.dumps(result, separators=(",", ":"))
        messages = copy.deepcopy(snapshot["messages"])
        if messages and messages[0].get("role") == "system":
            messages[0]["agent_prompt"] = True
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.tool_call_id,
                "name": ToolEnum.ASK_USER.value,
                "content": payload,
            }
        )
        await update_tool_call_by_id(
            engine,
            tool_call_id=str(tool_call.id),
            user_id=user_id,
            status=ToolCallStatusEnum.SUCCESS,
            result=result,
            model_context_payload=payload,
        )
        await redis.delete_pending_tool_continuation(str(tool_call.id))
        run["pending_tool_call_id"] = None
        run["result"] = ""
        primary = next(r for r in state["runs"].values() if not r["parent_id"])
        try:
            async with asyncio.timeout(remaining):
                await _resume_runs(execution, run, messages, primary)
        except (asyncio.CancelledError, TimeoutError) as exc:
            primary.update(
                status="cancelled", error="Agent execution was cancelled or exhausted its budget."
            )
            await execution.finish(primary)
            if isinstance(exc, TimeoutError):
                return
            raise
    finally:
        await redis.client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1,
            lock,
            lock_token,
        )


async def _resume_runs(execution, run, messages, primary):
    state = execution.state
    resumed = await execution.run(
        uuid.UUID(run["agent_id"]) if run["agent_id"] else None,
        run["instructions"],
        run["parent_id"],
        resumed=run,
        messages=messages,
    )
    primary = next(r for r in state["runs"].values() if not r["parent_id"])
    if run["parent_id"]:
        siblings = [r for r in state["runs"].values() if r["parent_id"] == primary["id"]]
        if resumed["status"] != "paused" and not any(r["status"] == "paused" for r in siblings):
            parent_messages = copy.deepcopy(primary["messages"])
            for message in parent_messages:
                if message.get("role") != "tool" or message.get("name") != "delegate_agents":
                    continue
                result = json.loads(message["content"])
                for output in result.get("runs", []):
                    child = state["runs"].get(output.get("id"))
                    if child:
                        output.update(
                            {
                                key: child.get(key)
                                for key in ["status", "result", "error", "version"]
                            }
                        )
                message["content"] = json.dumps(result)
            primary["result"] = ""
            primary = await execution.run(
                execution.primary_id, "", resumed=primary, messages=parent_messages
            )
    await execution.finish(primary)
