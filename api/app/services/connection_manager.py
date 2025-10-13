import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger("uvicorn.error")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.active_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")

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
            del self.active_tasks[key]
            return True
        elif task:
            # Task is already done, just remove it
            del self.active_tasks[key]
        return False

    def remove_task(self, user_id: str, node_id: str):
        key = self._get_task_key(user_id, node_id)
        if key in self.active_tasks:
            del self.active_tasks[key]
            logger.info(f"Completed stream task removed for node {node_id}")


manager = ConnectionManager()
