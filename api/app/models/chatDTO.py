from enum import Enum

from models.message import NodeTypeEnum
from pydantic import BaseModel


# https://openrouter.ai/docs/use-cases/reasoning-tokens
class EffortEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GenerateRequest(BaseModel):
    graph_id: str
    node_id: str
    model: str
    modelId: str | None = None
    stream_type: NodeTypeEnum
    title: bool = False
