import { defineStore } from 'pinia';

export const useGlobalSettingsStore = defineStore('GlobalSettings', () => {
    const defaultModel = 'google/gemini-2.0-flash-001';

    // -- Global Reasoning Settings --
    const effort = ref<'low' | 'medium' | 'high' | null>('medium');
    const excludeReasoning = ref(false);

    return {
        defaultModel,
        effort,
        excludeReasoning,
    };
});
