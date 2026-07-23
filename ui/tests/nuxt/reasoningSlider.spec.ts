import { mountSuspended } from '@nuxt/test-utils/runtime';
import { describe, expect, it } from 'vitest';
import { ReasoningEffortEnum } from '@/types/enums';
import ReasoningSlider from '@/components/ui/settings/utils/reasoningSlider.vue';

describe('reasoningSlider', () => {
    it('renders marker and accessibility state for an unsupported saved effort', async () => {
        const wrapper = await mountSuspended(ReasoningSlider, {
            props: {
                currentReasoningEffort: ReasoningEffortEnum.MAX,
                reasoningEfforts: 28,
            },
        });

        try {
            const slider = wrapper.get('[data-testid="reasoning-effort-slider"]');
            const markers = wrapper.findAll('[data-reasoning-effort]');

            expect(slider.attributes('aria-valuenow')).toBe('6');
            expect(slider.attributes('aria-valuetext')).toBe(
                'Max (unavailable for this model)',
            );
            expect(markers.map((marker) => marker.text())).toEqual([
                'None',
                'Minimal',
                'Low',
                'Medium',
                'High',
                'X-High',
                'Max',
            ]);
            expect(wrapper.get('[data-testid="reasoning-effort-marker-max"]').attributes())
                .toMatchObject({
                    'aria-disabled': 'true',
                    'data-selected': 'true',
                });
            expect(
                wrapper.get('[data-testid="reasoning-effort-marker-high"]').attributes(
                    'aria-disabled',
                ),
            ).toBe('false');
        } finally {
            wrapper.unmount();
        }
    });

    it('skips unsupported efforts for directional and boundary keys', async () => {
        const wrapper = await mountSuspended(ReasoningSlider, {
            props: {
                currentReasoningEffort: ReasoningEffortEnum.LOW,
                reasoningEfforts: 20,
            },
        });

        try {
            const slider = wrapper.get('[data-testid="reasoning-effort-slider"]');

            await slider.trigger('keydown', { key: 'ArrowRight' });
            expect(wrapper.emitted('update:reasoningEffort')?.at(-1)).toEqual([
                ReasoningEffortEnum.HIGH,
            ]);

            await wrapper.setProps({ currentReasoningEffort: ReasoningEffortEnum.HIGH });
            await slider.trigger('keydown', { key: 'Home' });
            expect(wrapper.emitted('update:reasoningEffort')?.at(-1)).toEqual([
                ReasoningEffortEnum.LOW,
            ]);

            await wrapper.setProps({ currentReasoningEffort: ReasoningEffortEnum.LOW });
            await slider.trigger('keydown', { key: 'End' });
            expect(wrapper.emitted('update:reasoningEffort')?.at(-1)).toEqual([
                ReasoningEffortEnum.HIGH,
            ]);
        } finally {
            wrapper.unmount();
        }
    });

    it('disables keyboard updates when no effort is supported', async () => {
        const wrapper = await mountSuspended(ReasoningSlider, {
            props: {
                currentReasoningEffort: ReasoningEffortEnum.NONE,
                reasoningEfforts: 0,
            },
        });

        try {
            const slider = wrapper.get('[data-testid="reasoning-effort-slider"]');

            expect(slider.attributes('aria-disabled')).toBe('true');
            await slider.trigger('keydown', { key: 'ArrowRight' });
            await slider.trigger('keydown', { key: 'Home' });
            await slider.trigger('keydown', { key: 'End' });
            expect(wrapper.emitted('update:reasoningEffort')).toBeUndefined();
        } finally {
            wrapper.unmount();
        }
    });
});
