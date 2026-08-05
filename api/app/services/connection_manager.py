import asyncio
import logging
from typing import Any

from database.redis.redis_ops import RedisManager
from fastapi import WebSocket
from services.websocket_broker import RedisWebSocketBroker, hash_broker_target

logger = logging.getLogger("uvicorn.error")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.active_tasks: dict[tuple[str, str], asyncio.Task] = {}
        self.client_user_ids: dict[str, str] = {}
        self.user_client_ids: dict[str, set[str]] = {}
        self.connection_locks: dict[str, asyncio.Lock] = {}
        self._broker: RedisWebSocketBroker | None = None

    async def start(self, redis_manager: RedisManager) -> None:
        if self._broker is None:
            self._broker = RedisWebSocketBroker(
                redis_manager,
                self._send_to_target,
                self._cancel_broker_task,
            )
        await self._broker.start()

    async def close(self) -> None:
        broker = self._broker
        self._broker = None
        if broker is not None:
            await broker.close()

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str | None = None):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_locks[client_id] = asyncio.Lock()
        if user_id:
            user_target = hash_broker_target(user_id)
            self.client_user_ids[client_id] = user_target
            self.user_client_ids.setdefault(user_target, set()).add(client_id)
        logger.info(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.connection_locks.pop(client_id, None)
            user_target = self.client_user_ids.pop(client_id, None)
            if user_target and user_target in self.user_client_ids:
                self.user_client_ids[user_target].discard(client_id)
                if not self.user_client_ids[user_target]:
                    del self.user_client_ids[user_target]
            logger.info(f"WebSocket disconnected: {client_id}")

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        user_target = hash_broker_target(user_id)
        await self._send_to_target(user_target, message)
        if self._broker is not None:
            await self._broker.publish_user_event(user_target, message)

    async def _send_to_target(self, user_target: str, message: dict[str, Any]) -> None:
        client_ids = list(self.user_client_ids.get(user_target, set()))
        for client_id in client_ids:
            websocket = self.active_connections.get(client_id)
            lock = self.connection_locks.get(client_id)
            if not websocket or not lock:
                continue
            try:
                async with lock:
                    await websocket.send_json(message)
            except Exception as exc:
                logger.warning("Failed to send WebSocket message to %s: %s", client_id, exc)
                self.disconnect(client_id)

    def _get_task_key(self, user_id: str, node_id: str) -> tuple[str, str]:
        return hash_broker_target(user_id), hash_broker_target(node_id)

    def add_task(self, task: asyncio.Task, user_id: str, node_id: str):
        key = self._get_task_key(user_id, node_id)
        self.active_tasks[key] = task
        logger.info("Started local stream task")

    async def cancel_task(self, user_id: str, node_id: str) -> bool:
        user_target, task_target = self._get_task_key(user_id, node_id)
        try:
            return await self._cancel_target_task(user_target, task_target)
        finally:
            if self._broker is not None:
                await self._broker.publish_task_cancel(user_target, task_target)

    async def _cancel_broker_task(self, user_target: str, task_target: str) -> None:
        await self._cancel_target_task(user_target, task_target)

    async def _cancel_target_task(self, user_target: str, task_target: str) -> bool:
        key = (user_target, task_target)
        task = self.active_tasks.get(key)
        if task and not task.done():
            task.cancel()
            # Wait for the task to acknowledge cancellation
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected
            logger.info("Cancelled local stream task")
            self._remove_target_task(user_target, task_target)
            return True
        elif task:
            self._remove_target_task(user_target, task_target)
        return False

    def remove_task(self, user_id: str, node_id: str):
        self._remove_target_task(*self._get_task_key(user_id, node_id))

    def _remove_target_task(self, user_target: str, task_target: str) -> None:
        key = (user_target, task_target)
        if key in self.active_tasks:
            del self.active_tasks[key]
            logger.info("Completed local stream task removed")


manager = ConnectionManager()
