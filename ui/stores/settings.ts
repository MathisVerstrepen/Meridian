import { defineStore } from 'pinia';

import type { GeneralSettings, ModelsSettings } from '@/types/settings';
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

        return {
            generalSettings,
            modelsSettings,

            setGeneralSettings: (settings: GeneralSettings) => {
                generalSettings.value = settings;
            },
            setModelsSettings: (settings: ModelsSettings) => {
                modelsSettings.value = settings;
            },
        };
    },
    {
        persist: {
            key: 'global-settings',
            storage: piniaPluginPersistedstate.localStorage(),
        },
    },
);
