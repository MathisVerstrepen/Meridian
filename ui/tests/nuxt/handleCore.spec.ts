import { mountSuspended } from '@nuxt/test-utils/runtime';
import { Position, useVueFlow, VueFlow } from '@vue-flow/core';
import { h } from 'vue';
import { describe, expect, it } from 'vitest';

import HandleCore, {
    getHandleHitZoneScale,
    MAX_HANDLE_HIT_ZONE_SCALE,
} from '@/components/ui/graph/node/utils/handleCore.vue';

describe('handleCore', () => {
    it('keeps the hit zone unchanged at and above normal zoom', () => {
        expect(getHandleHitZoneScale(1)).toBe(1);
        expect(getHandleHitZoneScale(2)).toBe(1);
    });

    it('compensates below normal zoom and caps growth', () => {
        expect(getHandleHitZoneScale(0.5)).toBe(2);
        expect(getHandleHitZoneScale(0.1)).toBe(MAX_HANDLE_HIT_ZONE_SCALE);
        expect(getHandleHitZoneScale(0)).toBe(1);
        expect(getHandleHitZoneScale(Number.NaN)).toBe(1);
    });

    it('reactively applies zoom compensation without changing visible handle styles', async () => {
        const flowId = 'handle-core-hit-zone-test';
        const wrapper = await mountSuspended(VueFlow, {
            props: {
                id: flowId,
                nodes: [
                    {
                        id: 'node-1',
                        type: 'hit-zone-test',
                        position: { x: 0, y: 0 },
                        data: {},
                    },
                ],
                edges: [],
            },
            slots: {
                'node-hit-zone-test': () =>
                    h(HandleCore, {
                        id: 'prompt_node-1',
                        type: 'source',
                        position: Position.Bottom,
                        style: { background: 'rgb(1, 2, 3)' },
                    }),
            },
        });
        const handle = wrapper.get<HTMLElement>('.zoom-aware-handle');

        expect(handle.element.style.background).toBe('rgb(1, 2, 3)');
        expect(handle.element.style.width).toBe('');
        expect(handle.element.style.height).toBe('');
        expect(handle.element.style.getPropertyValue('--handle-hit-zone-scale')).toBe('1');

        useVueFlow(flowId).setState({ viewport: { x: 0, y: 0, zoom: 0.5 } });
        await nextTick();

        expect(handle.element.style.getPropertyValue('--handle-hit-zone-scale')).toBe('2');
        expect(handle.element.style.background).toBe('rgb(1, 2, 3)');
        expect(handle.element.style.width).toBe('');
        expect(handle.element.style.height).toBe('');

        wrapper.unmount();
    });
});
