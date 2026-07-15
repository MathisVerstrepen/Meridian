import type { CompactModelCatalogResponse, CompactModelInfo } from '../../app/types/modelCatalog';

export const MODEL_CATALOG_FIXTURE_ROUTE = '/auth/model-catalog-fixture';
export const MODEL_CATALOG_FIXTURE_MODEL_COUNT = 500;

const namedModels: CompactModelInfo[] = [
    {
        id: 'fixture-text',
        name: 'Alpha Text',
        pricing: { prompt: '0', completion: '0' },
        capabilities: 1,
        created: '2024-01-01T00:00:00Z',
    },
    {
        id: 'fixture-image',
        name: 'Bravo Image',
        pricing: { prompt: '0.000001', completion: '0', image: '0.02' },
        capabilities: 2,
    },
    {
        id: 'fixture-video',
        name: 'Charlie Video',
        pricing: { prompt: '0', completion: '0' },
        capabilities: 4,
    },
    {
        id: 'fixture-text-image',
        name: 'Delta Text Image',
        pricing: { prompt: '0.000001', completion: '0.000002', image: '0.03' },
        capabilities: 3,
    },
    {
        id: 'fixture-text-video',
        name: 'Echo Text Video',
        pricing: { prompt: '0.000001', completion: '0.000002' },
        capabilities: 5,
    },
    {
        id: 'fixture-image-video',
        name: 'Foxtrot Image Video',
        pricing: { prompt: '0', completion: '0', image: '0' },
        capabilities: 6,
    },
    {
        id: 'fixture-all-capabilities',
        name: 'Zulu All Capabilities',
        pricing: { prompt: '0.000003', completion: '0.000006', image: '0.04' },
        capabilities: 255,
        supportedTools: 127,
        reasoningEfforts: -1,
        provider: 'github_copilot',
        icon: 'github-copilot',
        created: '2026-07-15T00:00:00Z',
        contextLength: 128000,
    },
    {
        id: 'fixture-unknown-bits-only',
        name: 'Unknown Bits Only',
        pricing: { prompt: '0', completion: '0' },
        capabilities: 128,
        supportedTools: 64,
    },
];

const generatedModels: CompactModelInfo[] = Array.from(
    { length: MODEL_CATALOG_FIXTURE_MODEL_COUNT - namedModels.length },
    (_, offset) => {
        const index = offset + namedModels.length;
        return {
            id: `fixture-generated-${index}`,
            name: `Generated Model ${String(index).padStart(3, '0')}`,
            pricing: {
                prompt: index % 3 === 0 ? '0' : '0.000001',
                completion: index % 5 === 0 ? '0' : '0.000002',
            },
            capabilities: 1 | (index % 4 === 0 ? 8 : 0) | (index % 6 === 0 ? 16 : 0),
            ...(index % 7 === 0 ? { reasoningEfforts: 28 } : {}),
        };
    },
);

export const MODEL_CATALOG_FIXTURE_RESPONSE: CompactModelCatalogResponse = {
    version: 1,
    data: [...namedModels, ...generatedModels],
    warnings: [
        {
            provider: 'github_copilot',
            title: 'Fixture provider warning',
            message: 'Reconnect the fixture provider to refresh its catalog.',
            actionLabel: 'Reconnect',
            actionUrl: '/settings?tab=Providers',
        },
    ],
};

export const MODEL_CATALOG_MODALITY_EXPECTATIONS = {
    'fixture-text': ['text'],
    'fixture-image': ['image'],
    'fixture-video': ['video'],
    'fixture-text-image': ['text', 'image'],
    'fixture-text-video': ['text', 'video'],
    'fixture-image-video': ['image', 'video'],
    'fixture-all-capabilities': ['text', 'image', 'video'],
    'fixture-unknown-bits-only': [],
} as const;
