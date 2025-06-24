from typing import List, Optional
from pydantic import BaseModel
from enum import Enum

from models.chatDTO import EffortEnum


class ModelsDropdownSortBy(str, Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"


class GeneralSettings(BaseModel):
    openChatViewOnNewCanvas: bool
    alwaysThinkingDisclosures: bool = False


class AccountSettings(BaseModel):
    openRouterApiKey: Optional[str] = None


class ModelsSettings(BaseModel):
    defaultModel: str
    excludeReasoning: bool
    globalSystemPrompt: str
    reasoningEffort: Optional[EffortEnum] = None
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


class BlockSettings(BaseModel):
    wheel: List[str]


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
    account: AccountSettings
    models: ModelsSettings
    modelsDropdown: ModelsDropdownSettings
    block: BlockSettings
    blockParallelization: BlockParallelizationSettings
