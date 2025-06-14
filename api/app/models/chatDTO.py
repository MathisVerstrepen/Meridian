from pydantic import BaseModel
from enum import Enum


# https://openrouter.ai/docs/use-cases/reasoning-tokens
class EffortEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Reasoning(BaseModel):
    effort: EffortEnum = EffortEnum.MEDIUM
    exclude: bool = False


class GenerateRequest(BaseModel):
    graph_id: str
    node_id: str
    model: str
    reasoning: Reasoning
    system_prompt: str = ""
    title: bool = False