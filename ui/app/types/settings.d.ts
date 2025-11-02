import type {
    ReasoningEffortEnum,
    NodeTypeEnum,
    ModelsDropdownSortBy,
    PDFEngine,
} from '@/types/enums';

export interface GeneralSettings {
    openChatViewOnNewCanvas: boolean;
    alwaysThinkingDisclosures: boolean;
    includeThinkingInContext: boolean;
    enableMessageCollapsing: boolean;
    defaultNodeType: NodeTypeEnum;
}

export interface AccountSettings {
    openRouterApiKey: string | null;
}

export interface SystemPrompt {
    id: string;
    name: string;
    prompt: string;
    enabled: boolean;
    editable: boolean;
    reference: string | null;
}

export interface ModelsSettings {
    defaultModel: string;
    excludeReasoning: boolean;
    systemPrompt: SystemPrompt[];
    reasoningEffort: ReasoningEffortEnum | null;
    maxTokens: number | null;
    temperature: number | null;
    topP: number | null;
    topK: number | null;
    frequencyPenalty: number | null;
    presencePenalty: number | null;
    repetitionPenalty: number | null;
}

export interface AppearanceSettings {
    theme: 'light' | 'dark' | 'oled' | 'standard';
    accentColor: string;
}

export interface ModelsDropdownSettings {
    sortBy: ModelsDropdownSortBy;
    hideFreeModels: boolean;
    hidePaidModels: boolean;
    pinnedModels: string[];
}

export interface WheelSlot {
    name: string;
    mainBloc: NodeTypeEnum | null;
    options: NodeTypeEnum[];
}

export interface BlockSettings {
    contextWheel: WheelSlot[];
}

export interface BlockParallelizationSettings {
    models: {
        model: string;
    }[];
    aggregator: {
        prompt: string;
        model: string;
    };
}

export interface Route {
    id: string;
    name: string;
    description: string;
    modelId: string;
    icon: string;
    customPrompt: string;
    overrideGlobalPrompt: boolean;
}

export interface RouteGroup {
    id: string;
    name: string;
    routes: Route[];
    isLocked: boolean;
    isDefault: boolean;
}

export interface BlockRoutingSettings {
    routeGroups: RouteGroup[];
}

export interface BlockGithubSettings {
    autoPull: boolean;
}

export interface BlockAttachmentSettings {
    pdf_engine: PDFEngine;
}

export interface BlockContextMergerSettings {
    merger_mode: ContextMergerModeEnum;
    last_n: number;
    summarizer_model: string;
}

export interface ToolsSettings {
    defaultSelectedTools: string[];
}

export interface ToolsWebSearchSettings {
    numResults: number;
    ignoredSites: string[];
    preferredSites: string[];
    customApiKey: string | null;
    forceCustomApiKey: boolean;
}

export interface ToolsLinkExtractionSettings {
    maxLength: number;
}

export interface Settings {
    general: GeneralSettings;
    account: AccountSettings;
    appearance: AppearanceSettings;
    models: ModelsSettings;
    modelsDropdown: ModelsDropdownSettings;
    block: BlockSettings;
    blockAttachment: BlockAttachmentSettings;
    blockParallelization: BlockParallelizationSettings;
    blockRouting: BlockRoutingSettings;
    blockGithub: BlockGithubSettings;
    blockContextMerger: BlockContextMergerSettings;
    tools: ToolsSettings;
    toolsWebSearch: ToolsWebSearchSettings;
    toolsLinkExtraction: ToolsLinkExtractionSettings;
}
