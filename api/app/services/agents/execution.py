"""Bounded execution of an independent main model and optional profile subagents."""

import asyncio
import copy
import json
import time
import uuid
from contextlib import aclosing
from datetime import datetime, timezone
from types import SimpleNamespace

from database.pg.agent_ops.tables import usage
from models.message import NodeTypeEnum
from pydantic import BaseModel
from schemas.agents import DelegationBatch, DelegationLimits
from services.agents.execution_state import ExecutionState
from services.agents.library import fail, resolve_profile
from services.agents.node_policy import MAIN_MODEL_PROMPT, authorize_node, main_model_profile
from services.agents.runtime import AgentPolicy, current_policy, permitted_tools
from services.inference import resolve_model_provider
from services.providers.message_serialization import message_to_wire
from sqlalchemy import insert


class StructuredAnswer(BaseModel):
    response: str


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_delegation_model(model, available_models):
    # First release uses the native OpenAI-compatible function interface through OpenRouter.
    if resolve_model_provider(model).value != "openrouter":
        fail(
            "Subagents require an OpenRouter model with tool calling. Choose a supported main "
            "model, or select a Team without active Agents."
        )
    entry = next(
        (
            m
            for m in available_models or []
            if (m.get("id") if isinstance(m, dict) else getattr(m, "id", None)) == model
        ),
        None,
    )
    parameters = (
        entry.get("toolsSupport", False)
        if isinstance(entry, dict)
        else getattr(entry, "toolsSupport", False)
    )
    if entry is None or not parameters:
        fail(
            f"{model} does not advertise tool calling. "
            "Select a tool-capable main model to use subagents."
        )


class AgentExecution(ExecutionState):
    def __init__(
        self,
        *,
        engine,
        websocket,
        request,
        user_id,
        graph_config,
        credentials,
        messages,
        http_client,
        redis_manager,
        available_models,
        state=None,
        sandbox_input_files=None,
        sandbox_input_warnings=None,
        file_hashes=None,
        neo4j_driver=None,
    ):
        self.engine, self.websocket, self.request = engine, websocket, request
        self.user_id = uuid.UUID(str(user_id))
        self.config, self.credentials = graph_config, credentials
        self.messages = [message_to_wire(m) for m in messages]
        self.http_client, self.redis = http_client, redis_manager
        self.available_models = available_models
        self.neo4j_driver = neo4j_driver
        self.limits = DelegationLimits()
        self.semaphore = asyncio.Semaphore(self.limits.concurrency)
        self.state = state or {
            "id": str(uuid.uuid4()),
            "runs": {},
            "calls": 0,
            "rounds": 0,
            "elapsed_seconds": 0.0,
            "status": "running",
        }
        self.state.setdefault("context_messages", copy.deepcopy(self.messages))
        from services.providers.common import serialize_sandbox_input_files

        self.state.setdefault(
            "sandbox_input_files", serialize_sandbox_input_files(sandbox_input_files or [])
        )
        self.state.setdefault("sandbox_input_warnings", sandbox_input_warnings or [])
        self.state.setdefault("file_hashes", file_hashes or {})
        self.pool = []
        self.started = time.monotonic()
        self.lock = asyncio.Lock()

    async def authorize(self):
        await authorize_node(self)

    async def main_tools(self):
        from services.agents.main_tools import resolve_main_tools

        return await resolve_main_tools(self)

    async def delegate(self, arguments, req):
        batch = DelegationBatch.model_validate(arguments)
        await self.authorize()
        if self.state["rounds"] >= self.limits.rounds:
            raise ValueError("Agent delegation round limit reached.")
        if self.state["calls"] + len(batch.calls) > self.limits.total_calls:
            raise ValueError("Agent total subagent call limit reached.")
        allowed = {member["id"] for member in self.pool}
        if any(str(call.agent_id) not in allowed for call in batch.calls):
            raise PermissionError(
                "Delegation rejected: Agent is outside this node's authorized subagent pool."
            )
        self.state["rounds"] += 1
        self.state["calls"] += len(batch.calls)
        parent_policy = current_policy.get()

        async def launch(call):
            async with self.semaphore:
                # Recheck the live membership, owner and lifecycle immediately before launch.
                await self.authorize()
                if str(call.agent_id) not in {member["id"] for member in self.pool}:
                    raise PermissionError("Subagent authorization changed before launch.")
                return await self.run(call.agent_id, call.instructions, parent_policy.run_id)

        results = await asyncio.gather(
            *(launch(call) for call in batch.calls), return_exceptions=True
        )
        outputs = []
        for call, result in zip(batch.calls, results):
            if isinstance(result, BaseException):
                outputs.append(
                    {"agent_id": str(call.agent_id), "status": "failed", "error": str(result)}
                )
            else:
                outputs.append(
                    {
                        key: result.get(key)
                        for key in [
                            "id",
                            "agent_id",
                            "name",
                            "version",
                            "instructions",
                            "status",
                            "result",
                            "error",
                        ]
                    }
                )
        if any(output.get("status") == "paused" for output in outputs):
            parent_policy.paused = True
        return {"runs": outputs}

    async def run(self, agent_id, instructions, parent_id=None, *, resumed=None, messages=None):
        from services.inference_requests import build_inference_request, stream_inference_response
        from services.reasoning_effort import get_model_reasoning_efforts
        from services.stream import _append_tool_guides, _deserialize_sandbox_input_files

        if parent_id is None:
            profile = main_model_profile(
                self.node_config, self.available_models, await self.main_tools()
            )
            row = {"version": None}
        else:
            async with self.engine.begin() as conn:
                row, profile = await resolve_profile(conn, self.user_id, agent_id, execute=True)
                if resumed is None:
                    await conn.execute(
                        insert(usage).values(
                            id=uuid.uuid4(), agent_id=agent_id, user_id=self.user_id
                        )
                    )
        run = resumed or {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "agent_id": str(agent_id) if agent_id else None,
            "name": profile.name,
            "handle": profile.handle,
            "version": row["version"],
            "instructions": instructions,
            "started_at": now(),
            "result": "",
            "tool_calls": [],
            "usage": [],
            "attempts": 0,
        }
        run["selected_tools"] = [tool.value for tool in permitted_tools(profile.tools)]
        run.update(
            status="running",
            version=row["version"],
            name=profile.name,
            handle=profile.handle,
            error=None,
        )
        self.state["runs"][run["id"]] = run
        config = self.config.model_copy(deep=True)
        for key, value in profile.model_settings.model_dump().items():
            if key in type(config).model_fields and value is not None:
                setattr(config, key, value)
        prompt = "\n\n".join(layer.text for layer in profile.prompt_stack if layer.enabled)
        tools = permitted_tools(profile.tools)
        prompt = _append_tool_guides(
            prompt, tools, [SimpleNamespace(data=self.node_data)] if parent_id is None else None
        )
        if parent_id is None:
            prompt = (
                (
                    MAIN_MODEL_PROMPT
                    if self.pool
                    else "Respond to the user using the conversation context."
                )
                + "\n\n"
                + prompt
            )
        if parent_id is None and self.pool:
            prompt += "\nAvailable subagents (presentation order only):\n" + json.dumps(self.pool)
        wire = copy.deepcopy(messages or self.messages)
        # Keep existing global/graph prompts and append this profile's ordered instructions.
        wire = [m for m in wire if not m.get("agent_prompt")]
        wire.insert(0, {"role": "system", "content": prompt, "agent_prompt": True})
        if instructions and not resumed:
            wire.append({"role": "user", "content": instructions})

        async def record_tool(name, arguments, result):
            run["tool_calls"].append(
                {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "arguments": arguments,
                    "result": result,
                    "at": now(),
                }
            )
            await self.event(run)

        policy = AgentPolicy(
            self.state["id"],
            run["id"],
            str(agent_id) if agent_id else None,
            row["version"],
            tools,
            self.delegate if parent_id is None and self.pool else None,
            record_tool,
        )
        token = current_policy.set(policy)
        try:
            await self.event(run)
            models = [profile.model_settings.model] * (profile.model_settings.retry_count + 1)
            if profile.model_settings.fallback_model:
                models.append(profile.model_settings.fallback_model)
            for index, model in enumerate(models):
                run["attempts"] += 1
                run["model"] = model
                req = build_inference_request(
                    credentials=self.credentials,
                    model=model,
                    messages=[{k: v for k, v in m.items() if k != "agent_prompt"} for m in wire],
                    config=config,
                    user_id=str(self.user_id),
                    pg_engine=self.engine,
                    node_id=self.request.node_id,
                    graph_id=self.request.graph_id,
                    node_type=NodeTypeEnum.AGENT,
                    http_client=self.http_client,
                    pdf_engine=config.pdf_engine,
                    file_hashes=self.state["file_hashes"],
                    sandbox_input_files=_deserialize_sandbox_input_files(
                        self.state["sandbox_input_files"]
                    ),
                    sandbox_input_warnings=self.state["sandbox_input_warnings"],
                    selected_tools=tools,
                    available_models=self.available_models,
                    schema=StructuredAnswer if profile.model_settings.structured_output else None,
                    reasoning_efforts=get_model_reasoning_efforts(model, self.available_models),
                )
                final = {}
                try:
                    async with aclosing(
                        stream_inference_response(req, self.engine, self.redis, final)
                    ) as response_stream:
                        async for chunk in response_stream:
                            if "[ERROR]" in chunk:
                                raise RuntimeError(
                                    chunk.replace("[ERROR]", "").replace("[!ERROR]", "").strip()
                                )
                            run["result"] += chunk
                            if parent_id is None:
                                await self.websocket.send_json(
                                    {
                                        "type": "stream_chunk",
                                        "node_id": self.request.node_id,
                                        "payload": chunk,
                                    }
                                )
                            await self.websocket.send_json(
                                {
                                    "type": "agent_run_chunk",
                                    "node_id": self.request.node_id,
                                    "execution_id": self.state["id"],
                                    "run_id": run["id"],
                                    "payload": chunk,
                                }
                            )
                    run["messages"] = req.messages
                    # Mark the profile prompt so resume can replace it with current policy.
                    if run["messages"] and run["messages"][0].get("role") == "system":
                        run["messages"][0]["agent_prompt"] = True
                    run["pending_tool_call_id"] = final.get("pending_tool_call_id")
                    run["status"] = (
                        "paused"
                        if policy.paused or final.get("pending_tool_call_id")
                        else "completed"
                    )
                    break
                except Exception:
                    # Never repeat completed side effects on a retry or fallback.
                    if (
                        index == len(models) - 1
                        or run["tool_calls"]
                        or (parent_id is None and self.state["calls"])
                    ):
                        raise
                    run["result"] = ""
                finally:
                    if final.get("usage_data"):
                        run["usage"].append(final["usage_data"])
            run.setdefault("versions_used", []).append(row["version"])
            run["ended_at"] = now() if run["status"] != "paused" else None
        except asyncio.CancelledError:
            run.update(status="cancelled", ended_at=now())
            raise
        except Exception as exc:
            run.update(status="failed", error=str(exc), ended_at=now())
        finally:
            current_policy.reset(token)
            await self.event(run)
        return run

    async def execute(self):
        await self.authorize()
        try:
            async with asyncio.timeout(self.limits.budget_seconds):
                primary = await self.run(self.primary_id, "")
        except (asyncio.CancelledError, TimeoutError) as exc:
            self.state["status"] = "cancelled"
            primary = next((r for r in self.state["runs"].values() if not r["parent_id"]), None)
            if primary:
                primary["status"] = "cancelled"
                if isinstance(exc, TimeoutError):
                    primary["error"] = "Agent execution budget exhausted. Run a smaller task."
                await self.finish(primary)
            else:
                await self.persist()
            if isinstance(exc, TimeoutError):
                return
            raise
        await self.finish(primary)
