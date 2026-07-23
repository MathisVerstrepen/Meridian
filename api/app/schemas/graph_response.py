import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphEditorGraphV1(BaseModel):
    id: uuid.UUID
    name: str
    node_count: int
    folder_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None
    description: str | None = None
    temporary: bool = False
    pinned: bool = False
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    custom_instructions: list[str] = Field(default_factory=list)
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    repetition_penalty: float | None = None
    reasoning_effort: str | None = None


class GraphEditorNodeV1(BaseModel):
    id: str
    type: str
    position_x: float
    position_y: float
    width: str = "100px"
    height: str = "100px"
    parent_node_id: str | None = None
    data: dict[str, Any] | list[Any] | None = None


class GraphEditorEdgeV1(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    source_handle_id: str | None = None
    target_handle_id: str | None = None
    type: str | None = None
    label: str | None = None
    animated: bool = False
    style: dict[str, Any] | list[Any] | None = None
    data: dict[str, Any] | list[Any] | None = None


class GraphEditorResponseV1(BaseModel):
    version: Literal[1]
    graph: GraphEditorGraphV1
    nodes: list[GraphEditorNodeV1]
    edges: list[GraphEditorEdgeV1]
