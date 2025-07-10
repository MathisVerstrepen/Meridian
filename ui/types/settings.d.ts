import { ReasoningEffortEnum } from '@/types/enums';

export interface GeneralSettings {
    openChatViewOnNewCanvas: boolean;
    alwaysThinkingDisclosures: boolean;
    includeThinkingInContext: boolean;
}

export interface AccountSettings {
    openRouterApiKey: string | null;
}

export interface ModelsSettings {
    defaultModel: string;
    excludeReasoning: boolean;
    globalSystemPrompt: string;
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

import { ModelsDropdownSortBy } from '@/types/enums';

export interface ModelsDropdownSettings {
    sortBy: ModelsDropdownSortBy;
    hideFreeModels: boolean;
    hidePaidModels: boolean;
    pinnedModels: string[];
}

export interface BlockSettings {
    wheel: string[];
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

export interface Settings {
    general: GeneralSettings;
    account: AccountSettings;
    appearance: AppearanceSettings;
    models: ModelsSettings;
    modelsDropdown: ModelsDropdownSettings;
    block: BlockSettings;
    blockParallelization: BlockParallelizationSettings;
    blockRouting: BlockRoutingSettings;
}
