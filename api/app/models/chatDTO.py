from pydantic import BaseModel
from enum import Enum


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
