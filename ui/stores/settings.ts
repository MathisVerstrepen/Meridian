import { defineStore } from 'pinia';

import type {
    GeneralSettings,
    AccountSettings,
    AppearanceSettings,
    ModelsSettings,
    ModelsDropdownSettings,
    BlockSettings,
    BlockParallelizationSettings,
    BlockRoutingSettings,
    Settings,
} from '@/types/settings';

export const useSettingsStore = defineStore('settings', () => {
    const { updateUserSettings } = useAPI();
    const { error, success } = useToast();

    const settings = ref<Settings | null>(null);
    const isReady = ref(false);
    const hasChanged = ref(false);

    const generalSettings = computed<GeneralSettings>(
        () => settings.value?.general ?? ({} as GeneralSettings),
    );
    const accountSettings = computed<AccountSettings>(
        () => settings.value?.account ?? ({} as AccountSettings),
    );
    const appearanceSettings = computed<AppearanceSettings>(
        () => settings.value?.appearance ?? ({} as AppearanceSettings),
    );
    const modelsSettings = computed<ModelsSettings>(
        () => settings.value?.models ?? ({} as ModelsSettings),
    );
    const modelsDropdownSettings = computed<ModelsDropdownSettings>(
        () => settings.value?.modelsDropdown ?? ({} as ModelsDropdownSettings),
    );
    const blockSettings = computed<BlockSettings>(
        () => settings.value?.block ?? ({} as BlockSettings),
    );
    const blockParallelizationSettings = computed<BlockParallelizationSettings>(
        () => settings.value?.blockParallelization ?? ({} as BlockParallelizationSettings),
    );
    const blockRoutingSettings = computed(
        () => settings.value?.blockRouting ?? ({} as BlockRoutingSettings),
    );

    let isInitial = true;
    watch(
        settings,
        (newSettings) => {
            if (isInitial || !newSettings) {
                isInitial = false;
                return;
            }
            hasChanged.value = true;
        },
        { deep: true },
    );

    watch(
        () => appearanceSettings.value.theme,
        (theme) => {
            if (import.meta.client && theme) {
                localStorage.setItem('theme', theme);
            }
        },
    );

    watch(
        () => appearanceSettings.value.accentColor,
        (accentColor) => {
            if (import.meta.client && accentColor) {
                localStorage.setItem('accentColor', accentColor);
            }
        },
    );

    const setUserSettings = (newSettings: Settings | null) => {
        if (!newSettings) {
            console.warn('No settings provided to setUserSettings');
            settings.value = null;
            return;
        }
        settings.value = newSettings;
        isReady.value = true;
        hasChanged.value = false;
    };

    const triggerSettingsUpdate = async () => {
        if (!settings.value) {
            return;
        }
        try {
            await updateUserSettings(settings.value);
            success('Settings updated successfully', {
                title: 'Update Success',
            });
            hasChanged.value = false;
        } catch (err) {
            console.error('Failed to update user settings:', err);
            error('Failed to update user settings: ' + (err as Error).message, {
                title: 'Update Error',
            });
        }
    };

    return {
        generalSettings,
        accountSettings,
        appearanceSettings,
        modelsSettings,
        modelsDropdownSettings,
        blockSettings,
        blockParallelizationSettings,
        blockRoutingSettings,
        isReady,
        hasChanged,

        setUserSettings,
        triggerSettingsUpdate,
    };
});
