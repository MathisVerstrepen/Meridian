export interface GeneralSettings {
    openChatViewOnNewCanvas: boolean;
}

export interface ModelsSettings {
    defaultModel: string;
    effort: 'low' | 'medium' | 'high' | null;
    excludeReasoning: boolean;
    globalSystemPrompt: string;
}

import { ModelsSelectSortBy } from '@/types/enums';

export interface ModelsSelectSettings {
    sortBy: ModelsSelectSortBy;
    hideFreeModels: boolean;
    hidePaidModels: boolean;
    pinnedModels: string[];
}
