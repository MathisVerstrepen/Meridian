from pydantic import BaseModel
from enum import Enum
from typing import Optional


# https://openrouter.ai/docs/use-cases/reasoning-tokens
class EffortEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GenerateRequest(BaseModel):
    graph_id: str
    node_id: str
    model: str
    title: bool = False
    modelId: Optional[str] = None
