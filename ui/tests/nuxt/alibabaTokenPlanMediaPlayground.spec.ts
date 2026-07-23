import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { nextTick, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ComposePane from '@/components/ui/images/playground/composePane.vue';
import EditPane from '@/components/ui/images/playground/editPane.vue';
import VideoPane from '@/components/ui/images/playground/videoPane.vue';
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import type { ModelInfo } from '@/types/model';

const model = (
    id: string,
    name: string,
    provider: ModelInfo['provider'],
    outputModality: 'image' | 'video',
): ModelInfo => ({
    id,
    name,
    provider,
    icon: '',
    architecture: {
        input_modalities: [],
        output_modalities: [outputModality],
        modality: outputModality,
        tokenizer: '',
    },
    pricing: { prompt: '0', completion: '0' },
    billingType: provider === 'openrouter' ? 'metered' : 'subscription',
    requiresConnection: provider !== 'openrouter',
    supportsStructuredOutputs: false,
    supportsMeridianTools: false,
    supportedMeridianToolNames: [],
    toolsSupport: false,
    reasoningEfforts: 0,
});

const fixtures = {
    alibabaImage: model(
        'alibaba-token-plan/future-image-family-v9',
        'Future Alibaba Image',
        'alibaba_token_plan',
        'image',
    ),
    openRouterImage: model('openrouter/future-image-v9', 'OpenRouter Image', 'openrouter', 'image'),
    t2v: model(
        'alibaba-token-plan/happyhorse-future-t2v-v9',
        'HappyHorse T2V',
        'alibaba_token_plan',
        'video',
    ),
    i2v: model(
        'alibaba-token-plan/happyhorse-future-i2v-v9',
        'HappyHorse I2V',
        'alibaba_token_plan',
        'video',
    ),
    r2v: model(
        'alibaba-token-plan/happyhorse-future-r2v-v9',
        'HappyHorse R2V',
        'alibaba_token_plan',
        'video',
    ),
    openRouterVideo: model('openrouter/future-video-v9', 'OpenRouter Video', 'openrouter', 'video'),
};

const playgroundRefs = {
    aspectRatio: ref('16:9'),
    exceedsBatchLimit: ref(false),
    generationCount: ref(1),
    isSubmitting: ref(false),
    lastError: ref<string | null>(null),
    prompt: ref('A future scene'),
    promptHistory: ref<string[]>([]),
    resolution: ref('4K'),
    selectedModels: ref<string[]>([]),
    sourceImages: ref<FileSystemObject[]>([]),
    stylePreset: ref<string | number>('none'),
    customStylePresets: ref<Record<string, { label: string; suffix: string }>>({}),
    stylePresets: ref({ none: { label: 'None', suffix: '' } }),
    uploadInProgress: ref(false),
    variationCount: ref(1),
    activeJobs: ref([]),
};

const settingsRefs = {
    isReady: ref(true),
    toolsImageGenerationSettings: ref({
        defaultModel: fixtures.alibabaImage.id,
        defaultVideoModel: fixtures.t2v.id,
    }),
};
const generatedVideos = ref<GeneratedImageGalleryItem[]>([]);

const storeMethods = {
    addSourceFiles: vi.fn().mockResolvedValue({ uploaded: [], failed: 0 }),
    addGeneratedImageReference: vi.fn(() => false),
    addCustomStylePreset: vi.fn(),
    deleteCustomStylePreset: vi.fn(),
    applyPromptHistory: vi.fn(),
    clearPromptHistory: vi.fn(),
    loadCustomStylePresets: vi.fn().mockResolvedValue(undefined),
    loadPromptHistory: vi.fn(),
    removeSourceImage: vi.fn(),
    removePromptHistory: vi.fn(),
    reorderSourceImages: vi.fn(),
    selectOnlyModel: vi.fn(),
    setDefaultModel: vi.fn(() => {
        if (!playgroundRefs.selectedModels.value.length) {
            playgroundRefs.selectedModels.value = [settingsRefs.toolsImageGenerationSettings.value.defaultModel];
        }
    }),
    setSourceImageReorderActive: vi.fn(),
    setSourceImagesFromCloud: vi.fn(),
    submit: vi.fn(),
    toggleModel: vi.fn(),
    cancelJob: vi.fn(),
    clearFailedJobs: vi.fn(),
    dismissFailedJob: vi.fn(),
    hydrateActiveJobs: vi.fn().mockResolvedValue(undefined),
    retryFailedJob: vi.fn(),
    submitVideo: vi.fn(),
};

const modelStore = {
    filteredModels: Object.values(fixtures),
    filterCompatibleModels: (models: ModelInfo[], criteria: { outputModality?: string }) =>
        models.filter((item) => criteria.outputModality
            ? item.architecture.output_modalities.includes(criteria.outputModality)
            : true),
};

mockNuxtImport('useImagePlaygroundStore', () => () => ({
    refs: playgroundRefs,
    loadGallery: vi.fn(),
    ...storeMethods,
}));
mockNuxtImport('useModelStore', () => () => ({ refs: { isReady: ref(true) }, ...modelStore }));
mockNuxtImport('useSettingsStore', () => () => ({
    refs: settingsRefs,
    blockAttachmentSettings: { default_upload_folder: null },
}));
mockNuxtImport('storeToRefs', () => (store: { refs: object }) => store.refs);
mockNuxtImport('useToast', () => () => ({ error: vi.fn(), success: vi.fn() }));
mockNuxtImport('useGraphEvents', () => () => ({
    emit: vi.fn(),
    on: vi.fn(() => () => undefined),
}));
mockNuxtImport('useAPI', () => () => ({
    createImageGenerationJobs: vi.fn(),
    getImageGenerationJobStatus: vi.fn(),
    getVideoPlaygroundGallery: vi.fn(async () => ({
        items: generatedVideos.value,
        total: generatedVideos.value.length,
    })),
    deleteFileSystemObject: vi.fn(),
    createFolder: vi.fn(),
    editImagePlaygroundImage: vi.fn(),
    getFolderContents: vi.fn(),
    getRootFolder: vi.fn(),
    uploadFile: vi.fn(),
}));

const mountOptions = {
    global: {
        stubs: {
            UiIcon: true,
            UiUtilsBaseModal: true,
            UiImagesPlaygroundActiveJobsLane: true,
        },
    },
};

describe('Alibaba Token Plan Image Playground behavior', () => {
    beforeEach(() => {
        playgroundRefs.aspectRatio.value = '16:9';
        playgroundRefs.resolution.value = '4K';
        playgroundRefs.selectedModels.value = [];
        playgroundRefs.sourceImages.value = [];
        generatedVideos.value = [];
        settingsRefs.toolsImageGenerationSettings.value = {
            defaultModel: fixtures.alibabaImage.id,
            defaultVideoModel: fixtures.t2v.id,
        };
    });

    it('uses square 1K/2K image controls and documents the three-reference envelope', async () => {
        const wrapper = await mountSuspended(ComposePane, mountOptions);
        await nextTick();

        try {
            expect(playgroundRefs.aspectRatio.value).toBe('1:1');
            expect(playgroundRefs.resolution.value).toBe('1K');
            expect(wrapper.text()).toContain('1024 px');
            expect(wrapper.text()).toContain('2048 px');
            expect(wrapper.text()).not.toContain('4096 px');
            expect(wrapper.text()).toContain('Optional · max 3');
            expect(wrapper.text()).toContain('explicit 1024 × 1024 or 2048 × 2048 square size');
        } finally {
            wrapper.unmount();
        }
    });

    it('excludes Alibaba models from mask/selection Image Edit', async () => {
        settingsRefs.toolsImageGenerationSettings.value.defaultModel = fixtures.alibabaImage.id;
        const wrapper = await mountSuspended(EditPane, mountOptions);
        await nextTick();

        try {
            expect(wrapper.text()).toContain('OpenRouter Image');
            expect(wrapper.text()).not.toContain('Future Alibaba Image');
        } finally {
            wrapper.unmount();
        }
    });

    it.each([
        [fixtures.t2v.id, 'No references', 'Text-to-video does not accept image references.'],
        [fixtures.i2v.id, 'Exactly 1 first frame', 'output follows the first frame'],
        [fixtures.r2v.id, '1–8 ordered images', '[Image N] order'],
    ])('applies HappyHorse controls for %s', async (modelId, requirement, guidance) => {
        settingsRefs.toolsImageGenerationSettings.value.defaultVideoModel = modelId;
        playgroundRefs.sourceImages.value = modelId === fixtures.t2v.id
            ? [{
                id: 'reference-1',
                name: 'Reference',
                path: '/reference',
                type: 'file',
                created_at: '',
                updated_at: '',
                cached: false,
            }]
            : [];
        const wrapper = await mountSuspended(VideoPane, mountOptions);
        await nextTick();
        await wrapper.get('textarea').setValue('A future motion scene');

        try {
            expect(wrapper.text()).toContain(requirement);
            expect(wrapper.text()).toContain(guidance);
            expect(wrapper.text()).toContain('Audio managed by HappyHorse');
            expect(wrapper.text()).toContain('native API exposes no Meridian audio switch');
            expect(wrapper.text()).toContain('720p');
            expect(wrapper.text()).toContain('1080p');
            expect(wrapper.text()).toContain('Auto');
            expect(wrapper.text()).toContain('10s');
            expect(wrapper.text()).not.toContain('480p');
            expect(wrapper.text()).not.toContain('4K');
            const audioButton = wrapper.findAll('button').find((button) =>
                button.text().includes('Audio managed by HappyHorse'),
            );
            expect(audioButton?.attributes('disabled')).toBeDefined();
            const createButton = wrapper.findAll('button').find((button) => button.text() === 'Create');
            if (modelId === fixtures.t2v.id) {
                expect(playgroundRefs.sourceImages.value).toEqual([]);
                expect(createButton?.attributes('disabled')).toBeUndefined();
                expect(wrapper.text()).toContain('16:9');
            } else {
                expect(createButton?.attributes('disabled')).toBeDefined();
            }
            if (modelId === fixtures.i2v.id) expect(wrapper.text()).not.toContain('16:9');
        } finally {
            wrapper.unmount();
        }
    });

    it('retains generic OpenRouter video controls and wording', async () => {
        settingsRefs.toolsImageGenerationSettings.value.defaultVideoModel = fixtures.openRouterVideo.id;
        const wrapper = await mountSuspended(VideoPane, mountOptions);
        await nextTick();

        try {
            expect(wrapper.text()).toContain('480p');
            expect(wrapper.text()).toContain('4K');
            expect(wrapper.text()).toContain('Silent video');
            expect(wrapper.text()).not.toContain('Audio managed by HappyHorse');
        } finally {
            wrapper.unmount();
        }
    });

    it('labels persisted Alibaba video audio as provider-managed rather than silent', async () => {
        settingsRefs.toolsImageGenerationSettings.value.defaultVideoModel = fixtures.t2v.id;
        generatedVideos.value = [{
            id: 'generated-video-1',
            name: 'Generated video',
            path: '/generated-video-1.mp4',
            content_type: 'video/mp4',
            created_at: '2026-07-23T00:00:00Z',
            updated_at: '2026-07-23T00:00:00Z',
            model: fixtures.t2v.id,
            generate_audio: false,
            source_image_ids: [],
        }];
        const wrapper = await mountSuspended(VideoPane, mountOptions);
        await nextTick();

        try {
            expect(wrapper.text()).toContain('provider-managed audio');
            expect(wrapper.text()).not.toContain('· silent ·');
        } finally {
            wrapper.unmount();
        }
    });
});
