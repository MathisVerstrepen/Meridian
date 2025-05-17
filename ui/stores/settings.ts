import { defineStore } from 'pinia';

import type { GeneralSettings, ModelsSettings, ModelsSelectSettings } from '@/types/settings';
import { ModelsSelectSortBy } from '@/types/enums';
import { DEFAULT_SYSTEM_PROMPT } from '@/constants';

export const useSettingsStore = defineStore(
    'settings',
    () => {
        const generalSettings = ref<GeneralSettings>({
            openChatViewOnNewCanvas: true,
        });

        const modelsSettings = ref<ModelsSettings>({
            defaultModel: 'google/gemini-2.0-flash-001',
            effort: 'medium',
            excludeReasoning: false,
            globalSystemPrompt: DEFAULT_SYSTEM_PROMPT,
        });

        const modelsSelectSettings = ref<ModelsSelectSettings>({
            sortBy: ModelsSelectSortBy.DATE_DESC,
            hideFreeModels: false,
            hidePaidModels: false,
            pinnedModels: [],
        });

        return {
            generalSettings,
            modelsSettings,
            modelsSelectSettings,
        };
    },
    {
        persist: {
            key: 'global-settings',
            storage: piniaPluginPersistedstate.localStorage(),
        },
    },
);
