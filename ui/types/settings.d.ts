import { ReasoningEffortEnum } from '@/types/enums';

export interface GeneralSettings {
    openChatViewOnNewCanvas: boolean;
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

import { ModelsDropdownSortBy } from '@/types/enums';

export interface ModelsDropdownSettings {
    sortBy: ModelsDropdownSortBy;
    hideFreeModels: boolean;
    hidePaidModels: boolean;
    pinnedModels: string[];
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

export interface Settings {
    general: GeneralSettings;
    account: AccountSettings;
    models: ModelsSettings;
    modelsDropdown: ModelsDropdownSettings;
    blockParallelization: BlockParallelizationSettings;
}
