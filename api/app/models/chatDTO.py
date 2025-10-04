from enum import Enum

from pydantic import BaseModel
from models.message import NodeTypeEnum


# https://openrouter.ai/docs/use-cases/reasoning-tokens
class EffortEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SubtypeEnum(str, Enum):
    PARALLELIZATION_MODEL = "parallelization-model"
    PARALLELIZATION_AGGREGATOR = "parallelization-aggregator"


class GenerateRequest(BaseModel):
    graph_id: str
    node_id: str
    model: str
    modelId: str | None = None
    stream_type: NodeTypeEnum
    title: bool = False
    subtype: SubtypeEnum | None = None
