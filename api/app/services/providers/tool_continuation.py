from typing import Any

from database.redis.redis_ops import RedisManager
from services.providers.common import serialize_sandbox_input_files


def _normalize_selected_tool_values(selected_tools: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    for tool_value in selected_tools or []:
        value = str(getattr(tool_value, "value", tool_value) or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


async def persist_pending_tool_continuation(
    redis_manager: RedisManager,
    *,
    public_tool_call_id: str,
    req: Any,
    messages: list[dict[str, Any]],
) -> None:
    await redis_manager.set_pending_tool_continuation(
        public_tool_call_id,
        {
            "messages": messages,
            "model": req.model,
            "model_id": req.model_id,
            "config": req.config.model_dump(mode="json"),
            "user_id": req.user_id,
            "node_id": req.node_id,
            "graph_id": req.graph_id,
            "node_type": req.node_type.value,
            "file_hashes": req.file_hashes,
            "pdf_engine": req.pdf_engine,
            "selected_tools": _normalize_selected_tool_values(getattr(req, "selected_tools", None)),
            "sandbox_input_files": serialize_sandbox_input_files(
                getattr(req, "sandbox_input_files", None) or []
            ),
            "sandbox_input_warnings": getattr(req, "sandbox_input_warnings", None) or [],
        },
    )
