from enum import Enum
from typing import List, Optional

from models.chatDTO import EffortEnum
from models.message import NodeTypeEnum
from pydantic import BaseModel


class ModelsDropdownSortBy(str, Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"


class GeneralSettings(BaseModel):
    openChatViewOnNewCanvas: bool
    alwaysThinkingDisclosures: bool = False
    includeThinkingInContext: bool = False
    defaultNodeType: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT


class AccountSettings(BaseModel):
    openRouterApiKey: Optional[str] = None


class AppearanceSettings(BaseModel):
    theme: str = "standard"
    accentColor: str = "#eb5e28"


class ModelsSettings(BaseModel):
    defaultModel: str
    excludeReasoning: bool
    globalSystemPrompt: str
    generateMermaid: bool = True
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


class WheelSlot(BaseModel):
    name: str
    mainBloc: NodeTypeEnum | None
    options: list[NodeTypeEnum]


class BlockSettings(BaseModel):
    contextWheel: List[WheelSlot] = [
        WheelSlot(
            name="Slot 1",
            mainBloc=NodeTypeEnum.TEXT_TO_TEXT,
            options=[NodeTypeEnum.PROMPT],
        ),
        WheelSlot(
            name="Slot 2",
            mainBloc=NodeTypeEnum.ROUTING,
            options=[NodeTypeEnum.PROMPT],
        ),
        WheelSlot(
            name="Slot 3",
            mainBloc=NodeTypeEnum.PARALLELIZATION,
            options=[NodeTypeEnum.PROMPT],
        ),
        WheelSlot(
            name="Slot 4",
            mainBloc=None,
            options=[],
        ),
    ]


class BlockParallelizationModelSettings(BaseModel):
    model: str


class BlockParallelizationAggregatorSettings(BaseModel):
    prompt: str
    model: str


class BlockParallelizationSettings(BaseModel):
    models: List[BlockParallelizationModelSettings]
    aggregator: BlockParallelizationAggregatorSettings


class Route(BaseModel):
    id: str
    name: str
    description: str
    modelId: str
    icon: str
    customPrompt: str
    overrideGlobalPrompt: bool


class RouteGroup(BaseModel):
    id: str
    name: str
    routes: List[Route]
    isLocked: bool
    isDefault: bool


class BlockRoutingSettings(BaseModel):
    routeGroups: List[RouteGroup]


class BlockGithubSettings(BaseModel):
    autoPull: bool


class SettingsDTO(BaseModel):
    general: GeneralSettings
    account: AccountSettings
    appearance: AppearanceSettings
    models: ModelsSettings
    modelsDropdown: ModelsDropdownSettings
    block: BlockSettings
    blockParallelization: BlockParallelizationSettings
    blockRouting: BlockRoutingSettings = BlockRoutingSettings(routeGroups=[])
    blockGithub: BlockGithubSettings = BlockGithubSettings(autoPull=False)
