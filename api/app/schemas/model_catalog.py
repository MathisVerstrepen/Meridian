from typing import Literal, Optional

from models.inference import InferenceProviderEnum, ModelDiscoveryWarning
from pydantic import BaseModel, Field


class CompactModelPricing(BaseModel):
    prompt: str
    completion: str
    image: Optional[str] = None


class CompactModelInfo(BaseModel):
    id: str
    name: str
    pricing: CompactModelPricing
    capabilities: int
    icon: Optional[str] = None
    provider: InferenceProviderEnum = InferenceProviderEnum.OPENROUTER
    created: Optional[str] = None
    contextLength: Optional[int] = None
    supportedTools: int = 0
    reasoningEfforts: int = 0


class CompactModelCatalogResponse(BaseModel):
    version: Literal[1]
    data: list[CompactModelInfo]
    warnings: list[ModelDiscoveryWarning] = Field(default_factory=list)
