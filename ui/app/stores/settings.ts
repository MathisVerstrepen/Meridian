import { defineStore } from 'pinia';

import type {
    GeneralSettings,
    AccountSettings,
    AppearanceSettings,
    ModelsSettings,
    ModelsDropdownSettings,
    BlockSettings,
    BlockPromptSettings,
    BlockParallelizationSettings,
    BlockRoutingSettings,
    BlockGithubSettings,
    Settings,
    BlockAttachmentSettings,
    ToolsSettings,
    ToolsWebSearchSettings,
    ToolsLinkExtractionSettings,
    BlockContextMergerSettings,
    GenerationHistorySettings,
    ToolsImageGenerationSettings,
    ToolsVisualiseSettings,
} from '@/types/settings';
import { NODE_PRESET_SCHEMA_VERSION, type NodePresetSettings } from '@/types/nodePresets';
import type { NodePresetValidationIssue } from '@/utils/nodePresets';
import { validateNodePresetSettings } from '@/utils/nodePresets';

export const useSettingsStore = defineStore('settings', () => {
    const { updateUserSettings } = useAPI();
    const { error, success } = useToast();

    const settings = ref<Settings | null>(null);
    const isReady = ref(false);
    const hasChanged = ref(false);
    const nodePresetEditorIssues = ref<NodePresetValidationIssue[]>([]);

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
    const blockPromptSettings = computed<BlockPromptSettings>(
        () => settings.value?.blockPrompt ?? ({} as BlockPromptSettings),
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
    const generationHistorySettings = computed<GenerationHistorySettings>(
        () => settings.value?.generationHistory ?? ({} as GenerationHistorySettings),
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
    const toolsVisualiseSettings = computed<ToolsVisualiseSettings>(
        () => settings.value?.toolsVisualise ?? ({} as ToolsVisualiseSettings),
    );
    const nodePresetSettings = computed<NodePresetSettings>(() =>
        settings.value?.nodePresets ?? {
            schemaVersion: NODE_PRESET_SCHEMA_VERSION,
            presets: [],
        },
    );
    const nodePresetValidation = computed(() =>
        validateNodePresetSettings(nodePresetSettings.value),
    );
    const nodePresetSaveBlocked = computed(
        () => !nodePresetValidation.value.valid || nodePresetEditorIssues.value.length > 0,
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

    watch(
        () => appearanceSettings.value.customThemeColors,
        (colors) => {
            if (import.meta.client && colors) {
                localStorage.setItem('customThemeColors', JSON.stringify(colors));
            }
        },
        { deep: true },
    );

    const setUserSettings = (newSettings: Settings | null) => {
        if (!newSettings) {
            console.warn('No settings provided to setUserSettings');
            settings.value = null;
            return;
        }
        settings.value = newSettings;
        nodePresetEditorIssues.value = [];
        isReady.value = true;
        hasChanged.value = false;
    };

    const setNodePresetEditorIssues = (issues: NodePresetValidationIssue[]) => {
        nodePresetEditorIssues.value = issues;
    };

    const markSettingsChanged = () => {
        hasChanged.value = true;
    };

    const triggerSettingsUpdate = async () => {
        if (!settings.value) {
            return false;
        }

        const presetValidation = validateNodePresetSettings(settings.value.nodePresets);
        if (!presetValidation.valid || nodePresetEditorIssues.value.length > 0) {
            error('Fix Node Preset validation errors before saving.', {
                title: 'Invalid Node Presets',
            });
            return false;
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
            return true;
        } catch (err) {
            console.error('Failed to update user settings:', err);
            error('Failed to update user settings: ' + (err as Error).message, {
                title: 'Update Error',
            });
            return false;
        }
    };

    return {
        generalSettings,
        accountSettings,
        appearanceSettings,
        modelsSettings,
        modelsDropdownSettings,
        blockSettings,
        blockPromptSettings,
        blockAttachmentSettings,
        blockParallelizationSettings,
        blockRoutingSettings,
        blockGithubSettings,
        blockContextMergerSettings,
        generationHistorySettings,
        toolsSettings,
        toolsWebSearchSettings,
        toolsLinkExtractionSettings,
        toolsImageGenerationSettings,
        toolsVisualiseSettings,
        nodePresetSettings,
        nodePresetValidation,
        nodePresetEditorIssues,
        nodePresetSaveBlocked,
        isReady,
        hasChanged,

        setUserSettings,
        setNodePresetEditorIssues,
        markSettingsChanged,
        triggerSettingsUpdate,
    };
});
