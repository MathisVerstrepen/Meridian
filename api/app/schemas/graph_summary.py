import datetime
import uuid

from pydantic import BaseModel
from schemas.topology_preview import TopologyPreviewV1


class GraphSummary(BaseModel):
    id: uuid.UUID
    name: str
    folder_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    temporary: bool
    pinned: bool
    updated_at: datetime.datetime
    node_count: int
    topology_preview: TopologyPreviewV1


class GraphSummaryPage(BaseModel):
    items: list[GraphSummary]
    has_more: bool
    next_offset: int | None
