import { defineStore } from 'pinia';

import type { ModelInfo } from '@/types/model';
import { ModelsDropdownSortBy } from '@/types/enums';
import { DEFAULT_FALLBACK_MODEL } from '@/constants';

export const useModelStore = defineStore('Model', () => {
    const models = ref<ModelInfo[]>([]);
    const isReady = ref<boolean>(false);
    const filteredModels = ref<ModelInfo[]>([]);
    const { warning } = useToast();

    const getModel = (modelId: string) => {
        const model = models.value.find((model) => model.id === modelId);
        if (!model) {
            warning(
                `Model with id ${modelId} not found, using fallback model ${DEFAULT_FALLBACK_MODEL}.`,
                {
                    title: 'Model Not Found',
                },
            );
            return models.value.find((model) => model.id === DEFAULT_FALLBACK_MODEL) as ModelInfo;
        }
        return model;
    };

    const setModels = (newModels: ModelInfo[]) => {
        models.value = newModels;
        isReady.value = true;
    };

    const isModelPaid = (model: ModelInfo) => {
        if (model.billingType === 'subscription') {
            return true;
        }
        return model.pricing.completion !== '0';
    };

    const filterCompatibleModels = (
        sourceModels: ModelInfo[],
        options?: {
            outputModality?: 'text' | 'image';
            requireStructuredOutputs?: boolean;
            requireMeridianTools?: boolean;
            requiredToolNames?: string[];
            excludedProviders?: string[];
        },
    ) => {
        const outputModality = options?.outputModality ?? 'text';
        const excludedProviders = options?.excludedProviders ?? [];

        return sourceModels.filter((model) => {
            const outputs = model.architecture?.output_modalities ?? [];
            const matchesOutput =
                outputModality === 'image'
                    ? outputs.includes('image')
                    : !outputs.includes('image');

            if (!matchesOutput) {
                return false;
            }
            if (options?.requireStructuredOutputs && !model.supportsStructuredOutputs) {
                return false;
            }
            if (options?.requireMeridianTools && !model.supportsMeridianTools) {
                return false;
            }
            if (
                options?.requiredToolNames?.length &&
                !options.requiredToolNames.every((toolName) =>
                    model.supportedMeridianToolNames?.includes(toolName),
                )
            ) {
                return false;
            }
            if (excludedProviders.includes(model.provider)) {
                return false;
            }
            return true;
        });
    };

    const sortModels = (sortBy: ModelsDropdownSortBy) => {
        const getCreatedTimestamp = (model: ModelInfo) => {
            const created = model.created ?? null;
            return created ? new Date(created).getTime() : 0;
        };

        switch (sortBy) {
            case ModelsDropdownSortBy.DATE_DESC:
                models.value.sort((a, b) => getCreatedTimestamp(b) - getCreatedTimestamp(a));
                break;
            case ModelsDropdownSortBy.DATE_ASC:
                models.value.sort((a, b) => getCreatedTimestamp(a) - getCreatedTimestamp(b));
                break;
            case ModelsDropdownSortBy.NAME_ASC:
                models.value.sort((a, b) => a.name.localeCompare(b.name));
                break;
            case ModelsDropdownSortBy.NAME_DESC:
                models.value.sort((a, b) => b.name.localeCompare(a.name));
                break;
            default:
                break;
        }
    };

    const triggerFilter = () => {
        const globalSettingsStore = useSettingsStore();
        const { modelsDropdownSettings } = storeToRefs(globalSettingsStore);

        filteredModels.value = models.value.filter((model) => {
            const isPaid = isModelPaid(model);
            if (modelsDropdownSettings.value.hideFreeModels && !isPaid) {
                return false;
            }
            if (modelsDropdownSettings.value.hidePaidModels && isPaid) {
                return false;
            }
            return true;
        });
    };

    return {
        models,
        filteredModels,
        isReady,

        getModel,
        setModels,
        isModelPaid,
        filterCompatibleModels,
        sortModels,
        triggerFilter,
    };
});
