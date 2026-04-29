import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("uvicorn.error")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.active_tasks: dict[str, asyncio.Task] = {}
        self.client_user_ids: dict[str, str] = {}
        self.user_client_ids: dict[str, set[str]] = {}
        self.connection_locks: dict[str, asyncio.Lock] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str | None = None):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.connection_locks[client_id] = asyncio.Lock()
        if user_id:
            self.client_user_ids[client_id] = user_id
            self.user_client_ids.setdefault(user_id, set()).add(client_id)
        logger.info(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.connection_locks.pop(client_id, None)
            user_id = self.client_user_ids.pop(client_id, None)
            if user_id and user_id in self.user_client_ids:
                self.user_client_ids[user_id].discard(client_id)
                if not self.user_client_ids[user_id]:
                    del self.user_client_ids[user_id]
            logger.info(f"WebSocket disconnected: {client_id}")

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        client_ids = list(self.user_client_ids.get(user_id, set()))
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

    def _get_task_key(self, user_id: str, node_id: str) -> str:
        return f"{user_id}:{node_id}"

    def add_task(self, task: asyncio.Task, user_id: str, node_id: str):
        key = self._get_task_key(user_id, node_id)
        self.active_tasks[key] = task
        logger.info(f"Started stream task for node {node_id} by user {user_id}")

    async def cancel_task(self, user_id: str, node_id: str) -> bool:
        key = self._get_task_key(user_id, node_id)
        task = self.active_tasks.get(key)
        if task and not task.done():
            task.cancel()
            # Wait for the task to acknowledge cancellation
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected
            logger.info(f"Cancelled stream task for node {node_id} by user {user_id}")
            self.remove_task(user_id, node_id)
            return True
        elif task:
            self.remove_task(user_id, node_id)
        return False

    def remove_task(self, user_id: str, node_id: str):
        key = self._get_task_key(user_id, node_id)
        if key in self.active_tasks:
            del self.active_tasks[key]
            logger.info(f"Completed stream task removed for node {node_id}")


manager = ConnectionManager()
