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

    const generalSettings = computed<Partial<GeneralSettings>>(
        () => settings.value?.general ?? {},
    );
    const accountSettings = computed<Partial<AccountSettings>>(
        () => settings.value?.account ?? {},
    );
    const appearanceSettings = computed<Partial<AppearanceSettings>>(
        () => settings.value?.appearance ?? {},
    );
    const modelsSettings = computed<Partial<ModelsSettings>>(
        () => settings.value?.models ?? {},
    );
    const modelsDropdownSettings = computed<Partial<ModelsDropdownSettings>>(
        () => settings.value?.modelsDropdown ?? {},
    );
    const blockSettings = computed<Partial<BlockSettings>>(
        () => settings.value?.block ?? {},
    );
    const blockPromptSettings = computed<Partial<BlockPromptSettings>>(
        () => settings.value?.blockPrompt ?? {},
    );
    const blockAttachmentSettings = computed<Partial<BlockAttachmentSettings>>(
        () => settings.value?.blockAttachment ?? {},
    );
    const blockParallelizationSettings = computed<Partial<BlockParallelizationSettings>>(
        () => settings.value?.blockParallelization ?? {},
    );
    const blockRoutingSettings = computed<Partial<BlockRoutingSettings>>(
        () => settings.value?.blockRouting ?? {},
    );
    const blockGithubSettings = computed<Partial<BlockGithubSettings>>(
        () => settings.value?.blockGithub ?? {},
    );
    const blockContextMergerSettings = computed<Partial<BlockContextMergerSettings>>(
        () => settings.value?.blockContextMerger ?? {},
    );
    const generationHistorySettings = computed<Partial<GenerationHistorySettings>>(
        () => settings.value?.generationHistory ?? {},
    );
    const toolsSettings = computed<Partial<ToolsSettings>>(
        () => settings.value?.tools ?? {},
    );
    const toolsWebSearchSettings = computed<Partial<ToolsWebSearchSettings>>(
        () => settings.value?.toolsWebSearch ?? {},
    );
    const toolsLinkExtractionSettings = computed<Partial<ToolsLinkExtractionSettings>>(
        () => settings.value?.toolsLinkExtraction ?? {},
    );
    const toolsImageGenerationSettings = computed<Partial<ToolsImageGenerationSettings>>(
        () => settings.value?.toolsImageGeneration ?? {},
    );
    const toolsVisualiseSettings = computed<Partial<ToolsVisualiseSettings>>(
        () => settings.value?.toolsVisualise ?? {},
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
            error('Failed to update user settings: ' + runtimeErrorMessage(err), {
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
