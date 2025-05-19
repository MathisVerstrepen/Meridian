import { defineStore } from 'pinia';

import type {
    GeneralSettings,
    ModelsSettings,
    ModelsSelectSettings,
    BlockParallelizationSettings,
} from '@/types/settings';
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

        const blockParallelizationSettings = ref<BlockParallelizationSettings>({
            models: [
                { model: modelsSettings.value.defaultModel },
                { model: modelsSettings.value.defaultModel },
            ],
            aggregator: {
                prompt: `You have been provided with a set of responses from various open-source models to the latest user query.
Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information
provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the
given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured,
coherent, and adheres to the highest standards of accuracy and reliability.`,
                model: modelsSettings.value.defaultModel,
            },
        });

        return {
            generalSettings,
            modelsSettings,
            modelsSelectSettings,
            blockParallelizationSettings,
        };
    },
    {
        persist: {
            key: 'global-settings',
            storage: piniaPluginPersistedstate.localStorage(),
        },
    },
);
