import { defineStore } from 'pinia';

import type { ModelInfo } from '@/types/model';

export const useModelStore = defineStore('Model', () => {
    const models = ref<ModelInfo[]>([]);

    return {
        models,
    };
});
