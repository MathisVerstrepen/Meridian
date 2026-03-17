from typing import Any

from pydantic import BaseModel


class ToolCallDetailResponse(BaseModel):
    id: str
    node_id: str
    model_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str
    status: str
    arguments: dict[str, Any] | list[Any]
    result: dict[str, Any] | list[Any]
    model_context_payload: str
    created_at: str | None = None
