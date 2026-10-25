import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { createPinia, setActivePinia } from 'pinia';
import { nextTick } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StreamRetryStatus from '@/components/ui/chat/utils/streamRetryStatus.vue';
import { useStreamRetryStore } from '@/stores/streamRetry';
import { useStreamStore } from '@/stores/stream';
import { NodeTypeEnum } from '@/types/enums';

mockNuxtImport('useWebSocket', () => () => ({ sendMessage: vi.fn(), connect: vi.fn() }));
mockNuxtImport('useCanvasSaveStore', () => () => ({ setNeedSave: vi.fn() }));
mockNuxtImport('useToast', () => () => ({ error: vi.fn() }));
mockNuxtImport('useUsageStore', () => () => ({ fetchUsage: vi.fn() }));
mockNuxtImport('useGraphEvents', () => () => ({ emit: vi.fn() }));
mockNuxtImport('useRoute', () => () => ({ params: { id: 'graph' } }));

const status = {
    attempt: 2,
    max_attempts: 4,
    delay_seconds: 3,
    message: 'Provider busy. Retrying in 3 seconds — attempt 2 of 4.',
};

describe('transient provider retry status', () => {
    beforeEach(() => setActivePinia(createPinia()));

    it('keeps parallel model status independent and clears only the matching model', () => {
        const store = useStreamRetryStore();
        store.update('node', status, 'model-a');
        store.update('node', { ...status, attempt: 3 }, 'model-b');
        store.update('node', null, 'model-a');
        expect(store.statuses.node).toEqual({ 'model-b': { ...status, attempt: 3 } });
        store.clear('node');
        expect(store.statuses.node).toBeUndefined();
        store.update('node', status);
        store.update('other-node', status);
        store.clearAll();
        expect(store.statuses).toEqual({});
    });

    it('ignores malformed status messages', () => {
        const store = useStreamRetryStore();
        for (const invalid of [
            'retry',
            {},
            { ...status, attempt: '2' },
            { ...status, attempt: 5 },
            { ...status, delay_seconds: -1 },
            { ...status, delay_seconds: Infinity },
        ])
            store.update('node', invalid);
        expect(store.statuses).toEqual({});
    });

    it('clears retry status when a stream starts or is cancelled without saving notices', async () => {
        const retryStore = useStreamRetryStore();
        const streamStore = useStreamStore();
        retryStore.update('node', status);
        const session = streamStore.preStreamSession('node', NodeTypeEnum.TEXT_TO_TEXT, true);
        expect(retryStore.statuses.node).toBeUndefined();
        retryStore.update('node', status);
        expect(session.response).toBe('');
        expect(session.isStreaming).toBe(true);
        await streamStore.cancelStream('node');
        expect(retryStore.statuses.node).toBeUndefined();
        expect(session.response).toBe('');
        expect(session.isStreaming).toBe(false);
    });

    it('renders an accessible status outside response content and removes it when cleared', async () => {
        const wrapper = await mountSuspended(StreamRetryStatus, { props: { nodeId: 'node' } });
        const store = useStreamRetryStore(wrapper.vm.$pinia);
        try {
            expect(wrapper.find('[role="status"]').exists()).toBe(false);
            store.update('node', status);
            await nextTick();
            expect(wrapper.get('[role="status"]').text()).toBe(status.message);
            store.update('node', null);
            await nextTick();
            expect(wrapper.find('[role="status"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });
});
