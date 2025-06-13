import { defineStore } from 'pinia';

import type { ModelInfo } from '@/types/model';
import { ModelsDropdownSortBy } from '@/types/enums';

export const useModelStore = defineStore('Model', () => {
    const models = ref<ModelInfo[]>([]);
    const isReady = ref<boolean>(false);
    const filteredModels = ref<ModelInfo[]>([]);

    const getModel = (modelId: string) => {
        const model = models.value.find((model) => model.id === modelId);
        if (!model) {
            throw new Error(`Model with id ${modelId} not found`);
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
