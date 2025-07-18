import { defineStore } from 'pinia';
import CryptoJS from 'crypto-js';

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
            if (process.client && theme) {
                localStorage.setItem('theme', theme);
            }
        },
    );

    watch(
        () => appearanceSettings.value.accentColor,
        (accentColor) => {
            if (process.client && accentColor) {
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

    const setOpenRouterApiKey = (key: string | null, user_id: string) => {
        if (!settings.value?.account) return;

        if (!key) {
            settings.value.account.openRouterApiKey = null;
            return;
        }
        const encryptedKey = CryptoJS.AES.encrypt(key, user_id).toString();
        settings.value.account.openRouterApiKey = encryptedKey;
    };

    const getOpenRouterApiKey = (user_id: string): string | null => {
        const encryptedKey = accountSettings.value.openRouterApiKey;
        if (!encryptedKey) {
            return null;
        }
        try {
            const decryptedBytes = CryptoJS.AES.decrypt(encryptedKey, user_id);
            return decryptedBytes.toString(CryptoJS.enc.Utf8) || null;
        } catch (err) {
            console.error('Failed to decrypt OpenRouter API key:', err);
            error('Failed to decrypt OpenRouter API key: ' + (err as Error).message, {
                title: 'Decryption Error',
            });
            return null;
        }
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
        setOpenRouterApiKey,
        getOpenRouterApiKey,
        triggerSettingsUpdate,
    };
});
