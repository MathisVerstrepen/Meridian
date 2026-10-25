"""Translate provider retry notifications to transient WebSocket status messages."""

from fastapi import WebSocket
from services.openrouter_retry import RetryCallback, RetryStatus


def retry_status_sender(
    websocket: WebSocket, node_id: str, model_id: str | None = None
) -> RetryCallback:
    async def send(status: RetryStatus | None) -> None:
        message: dict = {
            "type": "stream_retry_status",
            "node_id": node_id,
            "payload": status.payload() if status else None,
        }
        if model_id:
            message["model_id"] = model_id
        await websocket.send_json(message)

    return send
