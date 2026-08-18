import type { CompactModelCatalogResponse, CompactModelInfo } from '../../app/types/modelCatalog';
import {
    MODEL_CATALOG_FIXTURE_RESPONSE,
    MODEL_CATALOG_PERFORMANCE_MODEL_COUNT,
} from './modelCatalogFixture';

const generatedModels: CompactModelInfo[] = Array.from(
    {
        length:
            MODEL_CATALOG_PERFORMANCE_MODEL_COUNT - MODEL_CATALOG_FIXTURE_RESPONSE.data.length,
    },
    (_, offset) => {
        const index = offset + MODEL_CATALOG_FIXTURE_RESPONSE.data.length;
        const model = {
            id: `fixture-generated-${index}`,
            name: `Generated Model ${String(index).padStart(3, '0')}`,
            pricing: {
                prompt: index % 3 === 0 ? '0' : '0.000001',
                completion: index % 5 === 0 ? '0' : '0.000002',
            },
            capabilities: 1 | (index % 4 === 0 ? 8 : 0) | (index % 6 === 0 ? 16 : 0),
        };
        if (index % 7 === 0) Object.assign(model, { reasoningEfforts: 28 });
        return model;
    },
);

export const MODEL_CATALOG_PERFORMANCE_FIXTURE_RESPONSE: CompactModelCatalogResponse = {
    version: 1,
    data: [...MODEL_CATALOG_FIXTURE_RESPONSE.data, ...generatedModels],
    warnings: MODEL_CATALOG_FIXTURE_RESPONSE.warnings,
};
