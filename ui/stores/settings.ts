import { defineStore } from 'pinia';

import type {
    GeneralSettings,
    ModelsSettings,
    ModelsDropdownSettings,
    BlockParallelizationSettings,
    Settings,
} from '@/types/settings';
import { ModelsDropdownSortBy, ReasoningEffortEnum } from '@/types/enums';
import { DEFAULT_SYSTEM_PROMPT } from '@/constants';

export const useSettingsStore = defineStore('settings', () => {
    const { updateUserSettings } = useAPI();

    const generalSettings = ref<GeneralSettings>({
        openChatViewOnNewCanvas: true,
    } as GeneralSettings);

    const modelsSettings = ref<ModelsSettings>({
        defaultModel: 'google/gemini-2.5-flash-preview-05-20',
        reasoningEffort: ReasoningEffortEnum.MEDIUM,
        excludeReasoning: false,
        globalSystemPrompt: DEFAULT_SYSTEM_PROMPT,
        maxTokens: null,
        temperature: 0.7,
        topP: 1.0,
        topK: 40,
        frequencyPenalty: 0.0,
        presencePenalty: 0.0,
        repetitionPenalty: 1.0,
    } as ModelsSettings);

    const modelsDropdownSettings = ref<ModelsDropdownSettings>({
        sortBy: ModelsDropdownSortBy.DATE_DESC,
        hideFreeModels: false,
        hidePaidModels: false,
        pinnedModels: [],
    } as ModelsDropdownSettings);

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
    } as BlockParallelizationSettings);

    let isInitial = true;
    watch(
        () => ({
            general: generalSettings.value,
            models: modelsSettings.value,
            modelsDropdown: modelsDropdownSettings.value,
            blockParallelization: blockParallelizationSettings.value,
        }),
        (newSettings) => {
            if (isInitial) {
                isInitial = false;
                return;
            }
            updateUserSettings(newSettings as Settings).catch((error) => {
                console.error('Failed to update user settings:', error);
            });
        },
        { deep: true },
    );

    const setUserSettings = (settings: Settings | null) => {
        if (!settings) {
            console.warn('No settings provided to setUserSettings');
            return;
        }
        generalSettings.value = settings.general;
        modelsSettings.value = settings.models;
        modelsDropdownSettings.value = settings.modelsDropdown;
        blockParallelizationSettings.value = settings.blockParallelization;
    };

    return {
        generalSettings,
        modelsSettings,
        modelsDropdownSettings,
        blockParallelizationSettings,

        setUserSettings,
    };
});
