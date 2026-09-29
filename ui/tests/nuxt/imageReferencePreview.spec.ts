import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { flushPromises } from '@vue/test-utils';
import { createPinia, defineStore } from 'pinia';
import { ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ComposePane from '@/components/ui/images/playground/composePane.vue';
import ImageDetailModal from '@/components/ui/images/playground/imageDetailModal.vue';
import { useImagePlaygroundStore } from '@/stores/imagePlayground';
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';

const { getFileBlob } = vi.hoisted(() => ({ getFileBlob: vi.fn<() => Promise<Blob>>() }));

const useTestModelStore = defineStore('ReferencePreviewModels', () => ({
    isReady: ref(true),
    filteredModels: ref([]),
    filterCompatibleModels: () => [],
}));
const useTestSettingsStore = defineStore('ReferencePreviewSettings', () => ({
    isReady: ref(true),
    toolsImageGenerationSettings: ref({ defaultModel: '' }),
}));

mockNuxtImport('useModelStore', () => () => useTestModelStore());
mockNuxtImport('useSettingsStore', () => () => useTestSettingsStore());
mockNuxtImport('useAPI', () => () => ({
    getFileBlob,
    getCustomImageTonePresets: vi.fn().mockResolvedValue([]),
}));
mockNuxtImport('useWebSocket', () => () => ({ connect: vi.fn(), isConnected: ref(false) }));
mockNuxtImport('useToast', () => () => ({ error: vi.fn(), success: vi.fn() }));
mockNuxtImport('useGraphEvents', () => () => ({
    emit: vi.fn(),
    on: vi.fn(() => () => undefined),
}));

const reference = (id: string): FileSystemObject => ({
    id,
    name: `${id}.png`,
    path: `/References/${id}.png`,
    type: 'file',
    content_type: 'image/png',
    created_at: '2026-09-28T00:00:00Z',
    updated_at: '2026-09-28T00:00:00Z',
    cached: false,
});
const image: GeneratedImageGalleryItem = {
    ...reference('generated-image'),
    path: '/Images/generated-image.png',
    source_image_ids: ['reference-1'],
};
const fullReferenceUrl = '/api/auth/refresh/files/view/reference-1';
const referenceSelector = `a[href="${fullReferenceUrl}"]`;
const globalOptions = {
    stubs: { UiIcon: true, UiUtilsBaseModal: true },
};

const mountCompose = async () => {
    const pinia = createPinia();
    const store = useImagePlaygroundStore(pinia);
    store.sourceImages = [reference('reference-1'), reference('reference-2')];
    const wrapper = await mountSuspended(ComposePane, {
        global: { ...globalOptions, plugins: [pinia] },
        attachTo: document.body,
    });
    return { wrapper, store };
};

beforeEach(() => {
    getFileBlob.mockReset().mockResolvedValue(new Blob(['full image'], { type: 'image/png' }));
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:full-reference');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
});

afterEach(() => {
    vi.useRealTimers();
});

describe.each(['sidebar', 'image details'] as const)('%s reference preview', (surface) => {
    const mountSurface = async () => surface === 'sidebar'
        ? (await mountCompose()).wrapper
        : mountSuspended(ImageDetailModal, {
            props: { image, modelDisplayName: () => 'Test model' },
            global: globalOptions,
        });

    it('opens the authenticated full image in a reserved tab and releases the blob URL', async () => {
        const wrapper = await mountSurface();
        const open = vi.spyOn(window, 'open').mockReturnValue(window);
        const navigate = vi.spyOn(window.location, 'href', 'set').mockImplementation(() => undefined);
        const close = vi.spyOn(window, 'close').mockImplementation(() => undefined);
        window.opener = window;
        let resolveBlob!: (blob: Blob) => void;
        getFileBlob.mockReturnValueOnce(new Promise<Blob>((resolve) => { resolveBlob = resolve; }));
        vi.useFakeTimers();

        try {
            const link = wrapper.get(referenceSelector);
            expect(link.get('img').attributes('src')).toBe(`${fullReferenceUrl}?size=160x160`);
            await link.trigger('click');

            expect(open).toHaveBeenCalledExactlyOnceWith('about:blank', '_blank');
            expect(getFileBlob).toHaveBeenCalledExactlyOnceWith('reference-1');
            expect(window.opener).toBeNull();
            expect(navigate).not.toHaveBeenCalled();

            const fullImage = new Blob(['original image'], { type: 'image/png' });
            resolveBlob(fullImage);
            await flushPromises();

            expect(URL.createObjectURL).toHaveBeenCalledExactlyOnceWith(fullImage);
            expect(navigate).toHaveBeenCalledExactlyOnceWith('blob:full-reference');
            expect(close).not.toHaveBeenCalled();
            expect(wrapper.emitted('close')).toBeUndefined();
            await vi.advanceTimersByTimeAsync(59_999);
            expect(URL.revokeObjectURL).not.toHaveBeenCalled();
            await vi.advanceTimersByTimeAsync(1);
            expect(URL.revokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:full-reference');
        } finally {
            wrapper.unmount();
        }
    });

    it('retains the blob-opening fallback when the reserved tab is blocked', async () => {
        const wrapper = await mountSurface();
        const open = vi.spyOn(window, 'open').mockReturnValue(null);
        vi.useFakeTimers();

        try {
            await wrapper.get(referenceSelector).trigger('click');
            await flushPromises();

            expect(open).toHaveBeenNthCalledWith(1, 'about:blank', '_blank');
            expect(open).toHaveBeenNthCalledWith(2, 'blob:full-reference', '_blank', 'noopener,noreferrer');
            expect(getFileBlob).toHaveBeenCalledExactlyOnceWith('reference-1');
            await vi.advanceTimersByTimeAsync(60_000);
            expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:full-reference');
        } finally {
            wrapper.unmount();
        }
    });

    it('closes the reserved tab and uses the full-image URL when fetching fails', async () => {
        const wrapper = await mountSurface();
        const open = vi.spyOn(window, 'open').mockReturnValue(window);
        const close = vi.spyOn(window, 'close').mockImplementation(() => undefined);
        const error = new Error('File unavailable');
        const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
        getFileBlob.mockRejectedValueOnce(error);

        try {
            await wrapper.get(referenceSelector).trigger('click');
            await flushPromises();

            expect(log).toHaveBeenCalledWith('Reference image open failed:', error);
            expect(close).toHaveBeenCalledOnce();
            expect(open).toHaveBeenNthCalledWith(2, fullReferenceUrl, '_blank', 'noopener,noreferrer');
            expect(URL.createObjectURL).not.toHaveBeenCalled();
            expect(URL.revokeObjectURL).not.toHaveBeenCalled();
        } finally {
            wrapper.unmount();
        }
    });
});

describe('sidebar reference controls', () => {
    it('provides a named native keyboard-focusable link with visible focus', async () => {
        const { wrapper } = await mountCompose();
        const open = vi.spyOn(window, 'open').mockReturnValue(null);
        vi.useFakeTimers();

        try {
            const link = wrapper.get<HTMLAnchorElement>(referenceSelector);
            expect(link.attributes('aria-label')).toBe('Open reference reference-1.png in new tab');
            expect(link.attributes('target')).toBe('_blank');
            expect(link.attributes('rel')).toBe('noopener noreferrer');
            expect(link.element.tabIndex).toBe(0);
            expect(link.classes()).toContain('focus-visible:outline-2');
            link.element.focus();
            expect(document.activeElement).toBe(link.element);

            // Native links dispatch a click with detail 0 for keyboard activation.
            await link.trigger('click', { detail: 0 });
            await flushPromises();
            expect(getFileBlob).toHaveBeenCalledExactlyOnceWith('reference-1');
            expect(open).toHaveBeenCalledTimes(2);
            await vi.advanceTimersByTimeAsync(60_000);
        } finally {
            wrapper.unmount();
        }
    });

    it('removes only the selected reference without opening or fetching an image', async () => {
        const { wrapper, store } = await mountCompose();
        const open = vi.spyOn(window, 'open').mockReturnValue(null);

        try {
            const remove = wrapper.get('button[aria-label="Remove reference image"]');
            expect(remove.classes()).toContain('focus-visible:opacity-100');
            await remove.trigger('click');

            expect(store.sourceImageIds).toEqual(['reference-2']);
            expect(wrapper.find(referenceSelector).exists()).toBe(false);
            expect(open).not.toHaveBeenCalled();
            expect(getFileBlob).not.toHaveBeenCalled();
        } finally {
            wrapper.unmount();
        }
    });

    it('reorders references without previewing and keeps clicks available after dragging', async () => {
        const { wrapper, store } = await mountCompose();
        const open = vi.spyOn(window, 'open').mockReturnValue(null);
        const dataTransfer = { types: ['text/plain'], setData: vi.fn(), effectAllowed: 'none' };

        try {
            const cards = wrapper.findAll('[draggable="true"]');
            expect(cards).toHaveLength(2);
            const link = cards[0]!.get('a');
            expect(link.attributes('draggable')).toBe('false');
            expect(link.get('img').attributes('draggable')).toBe('false');
            await cards[0]!.trigger('dragstart', { dataTransfer });
            expect(store.isReorderingSourceImages).toBe(true);
            expect(dataTransfer.setData).toHaveBeenCalledWith('text/plain', 'reference-1');
            expect(dataTransfer.effectAllowed).toBe('move');
            await link.trigger('click');
            await cards[1]!.trigger('dragenter', { dataTransfer });
            expect(store.sourceImageIds).toEqual(['reference-2', 'reference-1']);
            await cards[1]!.trigger('drop', { dataTransfer });
            await cards[0]!.trigger('dragend', { dataTransfer });
            expect(store.isReorderingSourceImages).toBe(false);
            expect(open).not.toHaveBeenCalled();
            expect(getFileBlob).not.toHaveBeenCalled();

            vi.useFakeTimers();
            await wrapper.get(referenceSelector).trigger('click');
            await flushPromises();
            expect(getFileBlob).toHaveBeenCalledExactlyOnceWith('reference-1');
            await vi.advanceTimersByTimeAsync(60_000);
        } finally {
            wrapper.unmount();
        }
    });
});
