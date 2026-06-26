import datetime
import uuid
from typing import Any

from pydantic import BaseModel


class GenerationHistoryEntry(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    model: str | None
    selected_tools: list[str]
    preview: str
    is_active: bool


class GenerationHistoryDetail(GenerationHistoryEntry):
    snapshot: dict[str, Any] | list[Any]


class GenerationHistoryRestoreResponse(BaseModel):
    node_data: dict[str, Any] | list[Any]
