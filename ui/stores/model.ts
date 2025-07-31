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

    const sortModels = (sortBy: ModelsDropdownSortBy) => {
        switch (sortBy) {
            case ModelsDropdownSortBy.DATE_DESC:
                models.value.sort(
                    (a, b) => new Date(b.created).getTime() - new Date(a.created).getTime(),
                );
                break;
            case ModelsDropdownSortBy.DATE_ASC:
                models.value.sort(
                    (a, b) => new Date(a.created).getTime() - new Date(b.created).getTime(),
                );
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
            if (modelsDropdownSettings.value.hideFreeModels && model.pricing.completion === '0') {
                return false;
            }
            if (modelsDropdownSettings.value.hidePaidModels && model.pricing.completion !== '0') {
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
        sortModels,
        triggerFilter,
    };
});
