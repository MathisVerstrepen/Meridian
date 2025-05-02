import { defineStore } from 'pinia';

export const useGlobalSettingsStore = defineStore('GlobalSettings', () => {
    const defaultModel = 'google/gemini-2.0-flash-001';

    return {
        defaultModel,
    };
});
