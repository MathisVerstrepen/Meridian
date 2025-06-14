import { defineStore } from 'pinia';

import type {
    GeneralSettings,
    ModelsSettings,
    ModelsDropdownSettings,
    BlockParallelizationSettings,
    Settings,
} from '@/types/settings';

export const useSettingsStore = defineStore('settings', () => {
    const { updateUserSettings } = useAPI();

    const generalSettings = ref<GeneralSettings>() as globalThis.Ref<GeneralSettings>;
    const modelsSettings = ref<ModelsSettings>() as globalThis.Ref<ModelsSettings>;
    const modelsDropdownSettings =
        ref<ModelsDropdownSettings>() as globalThis.Ref<ModelsDropdownSettings>;
    const blockParallelizationSettings =
        ref<BlockParallelizationSettings>() as globalThis.Ref<BlockParallelizationSettings>;
    const isReady = ref(false);

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
        isReady.value = true;
    };

    return {
        generalSettings,
        modelsSettings,
        modelsDropdownSettings,
        blockParallelizationSettings,
        isReady,

        setUserSettings,
    };
});
