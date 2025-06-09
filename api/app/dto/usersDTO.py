from typing import List, Optional
from pydantic import BaseModel
from enum import Enum


class ReasoningEffortEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModelsDropdownSortBy(str, Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"


class GeneralSettings(BaseModel):
    openChatViewOnNewCanvas: bool


class ModelsSettings(BaseModel):
    defaultModel: str
    excludeReasoning: bool
    globalSystemPrompt: str
    reasoningEffort: Optional[ReasoningEffortEnum] = None
    maxTokens: Optional[int] = None
    temperature: Optional[float] = None
    topP: Optional[float] = None
    topK: Optional[int] = None
    frequencyPenalty: Optional[float] = None
    presencePenalty: Optional[float] = None
    repetitionPenalty: Optional[float] = None


class ModelsDropdownSettings(BaseModel):
    sortBy: ModelsDropdownSortBy
    hideFreeModels: bool
    hidePaidModels: bool
    pinnedModels: List[str]


class BlockParallelizationModelSettings(BaseModel):
    model: str


class BlockParallelizationAggregatorSettings(BaseModel):
    prompt: str
    model: str


class BlockParallelizationSettings(BaseModel):
    models: List[BlockParallelizationModelSettings]
    aggregator: BlockParallelizationAggregatorSettings


class SettingsDTO(BaseModel):
    general: GeneralSettings
    models: ModelsSettings
    modelsDropdown: ModelsDropdownSettings
    blockParallelization: BlockParallelizationSettings
