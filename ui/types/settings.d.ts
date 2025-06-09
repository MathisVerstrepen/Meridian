export interface GeneralSettings {
    openChatViewOnNewCanvas: boolean;
}

export interface ModelsSettings {
    defaultModel: string;
    effort: 'low' | 'medium' | 'high' | null;
    excludeReasoning: boolean;
    globalSystemPrompt: string;
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
