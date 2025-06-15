import { defineStore } from 'pinia';
import CryptoJS from 'crypto-js';

import type {
    GeneralSettings,
    AccountSettings,
    ModelsSettings,
    ModelsDropdownSettings,
    BlockParallelizationSettings,
    Settings,
} from '@/types/settings';

export const useSettingsStore = defineStore('settings', () => {
    const { updateUserSettings } = useAPI();

    const generalSettings = ref<GeneralSettings>() as globalThis.Ref<GeneralSettings>;
    const accountSettings = ref<AccountSettings>() as globalThis.Ref<AccountSettings>;
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
            account: accountSettings.value,
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
        accountSettings.value = settings.account;
        modelsSettings.value = settings.models;
        modelsDropdownSettings.value = settings.modelsDropdown;
        blockParallelizationSettings.value = settings.blockParallelization;
        isReady.value = true;
    };

    const setOpenRouterApiKey = (key: string | null, user_id: string) => {
        if (!key) {
            accountSettings.value.openRouterApiKey = null;
            return;
        }

        const encryptedKey = CryptoJS.AES.encrypt(key, user_id).toString();

        accountSettings.value.openRouterApiKey = encryptedKey;
    };

    const getOpenRouterApiKey = (user_id: string): string | null => {
        const encryptedKey = accountSettings.value.openRouterApiKey;
        if (!encryptedKey) {
            return null;
        }
        try {
            const decryptedBytes = CryptoJS.AES.decrypt(encryptedKey, user_id);
            const decryptedKey = decryptedBytes.toString(CryptoJS.enc.Utf8);
            return decryptedKey || null;
        } catch (error) {
            console.error('Failed to decrypt OpenRouter API key:', error);
            return null;
        }
    };

    return {
        generalSettings,
        modelsSettings,
        modelsDropdownSettings,
        blockParallelizationSettings,
        isReady,

        setUserSettings,
        setOpenRouterApiKey,
        getOpenRouterApiKey,
    };
});
