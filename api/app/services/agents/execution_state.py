"""Execution persistence, history snapshots and run-attributed WebSocket events."""

import copy
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from database.pg.agent_ops.tables import executions
from database.pg.models import GenerationHistory, Node, Settings
from models.message import NodeTypeEnum
from sqlalchemy import delete, insert, select, update


class ExecutionState:
    engine: Any
    websocket: Any
    request: Any
    user_id: uuid.UUID
    state: dict[str, Any]
    lock: Any
    started: float

    async def persist(self):
        async with self.lock:
            snapshot = copy.deepcopy(self.state)
            async with self.engine.begin() as conn:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                await conn.execute(
                    pg_insert(executions)
                    .values(
                        id=uuid.UUID(snapshot["id"]),
                        owner_id=self.user_id,
                        graph_id=uuid.UUID(self.request.graph_id),
                        node_id=self.request.node_id,
                        state=snapshot,
                    )
                    .on_conflict_do_update(
                        index_elements=["id"],
                        set_={"state": snapshot, "updated_at": datetime.now(timezone.utc)},
                    )
                )

    async def event(self, run, kind="agent_run"):
        await self.persist()
        await self.websocket.send_json(
            {
                "type": kind,
                "node_id": self.request.node_id,
                "graph_id": self.request.graph_id,
                "execution_id": self.state["id"],
                "run_id": run["id"],
                "payload": {k: copy.deepcopy(v) for k, v in run.items() if k != "messages"},
            }
        )

    async def finish(self, primary):
        self.state["status"] = primary["status"]
        self.state["elapsed_seconds"] += time.monotonic() - self.started
        await self.event(primary)
        public = {
            **{
                k: v
                for k, v in self.state.items()
                if k
                not in {
                    "context_messages",
                    "sandbox_input_files",
                    "sandbox_input_warnings",
                    "file_hashes",
                }
            },
            "runs": {
                key: {k: v for k, v in run.items() if k != "messages"}
                for key, run in self.state["runs"].items()
            },
        }
        totals = {
            key: sum(
                float(u.get(key) or 0) for run in self.state["runs"].values() for u in run["usage"]
            )
            for key in ["cost", "total_tokens", "prompt_tokens", "completion_tokens"]
        }
        async with self.engine.begin() as conn:
            data = (
                await conn.execute(
                    select(Node.data)
                    .where(
                        Node.graph_id == uuid.UUID(self.request.graph_id),
                        Node.id == self.request.node_id,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            data = {
                **data,
                "reply": primary["result"],
                "agentExecution": public,
                "usageData": totals,
            }
            if primary["status"] == "completed" and primary["result"]:
                history_id = uuid.uuid4()
                await conn.execute(
                    insert(GenerationHistory).values(
                        id=history_id,
                        user_id=self.user_id,
                        graph_id=uuid.UUID(self.request.graph_id),
                        node_id=self.request.node_id,
                        node_type=NodeTypeEnum.AGENT.value,
                        snapshot=data,
                        preview=primary["result"][:220],
                        model=primary["model"],
                        selected_tools=primary.get("selected_tools", []),
                    )
                )
                settings = (
                    await conn.execute(
                        select(Settings.settings_data).where(Settings.user_id == self.user_id)
                    )
                ).scalar_one_or_none() or {}
                limit = max(
                    1,
                    min(
                        100, int(settings.get("generationHistory", {}).get("max_saved_entries", 10))
                    ),
                )
                old_ids = (
                    (
                        await conn.execute(
                            select(GenerationHistory.id)
                            .where(
                                GenerationHistory.graph_id == uuid.UUID(self.request.graph_id),
                                GenerationHistory.node_id == self.request.node_id,
                            )
                            .order_by(
                                GenerationHistory.created_at.desc(), GenerationHistory.id.desc()
                            )
                            .offset(limit)
                        )
                    )
                    .scalars()
                    .all()
                )
                if old_ids:
                    await conn.execute(
                        delete(GenerationHistory).where(GenerationHistory.id.in_(old_ids))
                    )
                data["activeGenerationHistoryId"] = str(history_id)
            await conn.execute(
                update(Node)
                .where(
                    Node.graph_id == uuid.UUID(self.request.graph_id),
                    Node.id == self.request.node_id,
                )
                .values(data=data)
            )
        await self.websocket.send_json(
            {
                "type": "node_data_update",
                "graph_id": self.request.graph_id,
                "node_id": self.request.node_id,
                "payload": data,
            }
        )
        await self.websocket.send_json(
            {"type": "usage_data_update", "node_id": self.request.node_id, "payload": totals}
        )
        if primary["status"] == "failed" or primary.get("error"):
            await self.websocket.send_json(
                {
                    "type": "stream_error",
                    "node_id": self.request.node_id,
                    "payload": {"message": primary["error"]},
                }
            )
        else:
            await self.websocket.send_json(
                {
                    "type": "stream_end",
                    "node_id": self.request.node_id,
                    "payload": {"refresh_tool_usage": True},
                }
            )
