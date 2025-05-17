import { defineStore } from 'pinia';

import type { ModelInfo } from '@/types/model';
import { ModelsSelectSortBy } from '@/types/enums';

export const useModelStore = defineStore('Model', () => {
    const models = ref<ModelInfo[]>([]);

    const getModel = (modelId: string) => {
        const model = models.value.find((model) => model.id === modelId);
        if (!model) {
            throw new Error(`Model with id ${modelId} not found`);
        }
        return model;
    };

    const sortModels = (sortBy: ModelsSelectSortBy) => {
        switch (sortBy) {
            case ModelsSelectSortBy.DATE_DESC:
                models.value.sort(
                    (a, b) => new Date(b.created).getTime() - new Date(a.created).getTime(),
                );
                break;
            case ModelsSelectSortBy.DATE_ASC:
                models.value.sort(
                    (a, b) => new Date(a.created).getTime() - new Date(b.created).getTime(),
                );
                break;
            case ModelsSelectSortBy.NAME_ASC:
                models.value.sort((a, b) => a.name.localeCompare(b.name));
                break;
            case ModelsSelectSortBy.NAME_DESC:
                models.value.sort((a, b) => b.name.localeCompare(a.name));
                break;
            default:
                break;
        }
    };

    return {
        models,

        getModel,
        sortModels,
    };
});
