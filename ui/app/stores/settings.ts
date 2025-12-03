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
    BlockGithubSettings,
    Settings,
    BlockAttachmentSettings,
    ToolsSettings,
    ToolsWebSearchSettings,
    ToolsLinkExtractionSettings,
    BlockContextMergerSettings,
    ToolsImageGenerationSettings,
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
    const blockAttachmentSettings = computed<BlockAttachmentSettings>(
        () => settings.value?.blockAttachment ?? ({} as BlockAttachmentSettings),
    );
    const blockParallelizationSettings = computed<BlockParallelizationSettings>(
        () => settings.value?.blockParallelization ?? ({} as BlockParallelizationSettings),
    );
    const blockRoutingSettings = computed(
        () => settings.value?.blockRouting ?? ({} as BlockRoutingSettings),
    );
    const blockGithubSettings = computed<BlockGithubSettings>(
        () => settings.value?.blockGithub ?? ({} as BlockGithubSettings),
    );
    const blockContextMergerSettings = computed<BlockContextMergerSettings>(
        () => settings.value?.blockContextMerger ?? ({} as BlockContextMergerSettings),
    );
    const toolsSettings = computed<ToolsSettings>(
        () => settings.value?.tools ?? ({} as ToolsSettings),
    );
    const toolsWebSearchSettings = computed<ToolsWebSearchSettings>(
        () => settings.value?.toolsWebSearch ?? ({} as ToolsWebSearchSettings),
    );
    const toolsLinkExtractionSettings = computed<ToolsLinkExtractionSettings>(
        () => settings.value?.toolsLinkExtraction ?? ({} as ToolsLinkExtractionSettings),
    );
    const toolsImageGenerationSettings = computed<ToolsImageGenerationSettings>(
        () => settings.value?.toolsImageGeneration ?? ({} as ToolsImageGenerationSettings),
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

        // For each models.systemPrompt, if reference is not null, set prompt to ""
        settings.value.models.systemPrompt = settings.value.models.systemPrompt.map((sp) => {
            if (sp.reference) {
                return {
                    ...sp,
                    prompt: '',
                };
            }
            return sp;
        });

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
        blockAttachmentSettings,
        blockParallelizationSettings,
        blockRoutingSettings,
        blockGithubSettings,
        blockContextMergerSettings,
        toolsSettings,
        toolsWebSearchSettings,
        toolsLinkExtractionSettings,
        toolsImageGenerationSettings,
        isReady,
        hasChanged,

        setUserSettings,
        triggerSettingsUpdate,
    };
});
