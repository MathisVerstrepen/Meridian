import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h, reactive, ref } from 'vue';
import { useTeamMentions } from '@/composables/useTeamMentions';
import TeamMentionMenu from '@/components/ui/chat/teamMentionMenu.vue';
import type { AgentTeam } from '@/types/agent';

const stubs = vi.hoisted(() => ({
    store: {
        teams: Array<AgentTeam>(),
        library: Array<{ id: string; profile: { lifecycle: string } }>(),
        loadLibrary: vi.fn<() => Promise<void>>(),
    },
}));
mockNuxtImport('useAgentStore', () => () => stubs.store);
const team: AgentTeam = {
    id: 'default',
    name: 'Default Team',
    handle: 'default',
    is_default: true,
    description: 'Your regular helpers',
    members: ['active', 'draft'],
};
const Harness = defineComponent({
    emits: ['chosen'],
    setup(_, { emit }) {
        const editor = ref<HTMLDivElement | null>(null);
        const mentions = useTeamMentions(editor, (text) => emit('chosen', text));
        return () =>
            h('div', [
                h('div', {
                    ref: editor,
                    contenteditable: true,
                    onInput: () => mentions.sync(),
                    onKeydown: mentions.keydown,
                }),
                mentions.open.value
                    ? h(TeamMentionMenu, {
                          teams: mentions.suggestions.value,
                          activeIndex: mentions.activeIndex.value,
                          listId: mentions.listId,
                          query: mentions.query.value,
                          loading: mentions.loading.value,
                          error: mentions.error.value,
                          memberCount: mentions.memberCount,
                          onChoose: mentions.choose,
                          onRetry: mentions.retry,
                          onActive: (index: number) => {
                              mentions.activeIndex.value = index;
                          },
                      })
                    : null,
            ]);
    },
});
beforeEach(() => {
    stubs.store = reactive({
        teams: [],
        library: [],
        loadLibrary: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
    });
});
const mountPicker = () => mountSuspended(Harness, { global: { stubs: { UiIcon: true } } });

describe('Team mention loading and recovery', () => {
    it('shows loading, then eligible member counts when Teams arrive', async () => {
        let release: (() => void) | undefined;
        stubs.store.loadLibrary.mockImplementationOnce(
            () =>
                new Promise<void>((resolve) => {
                    release = resolve;
                }),
        );
        const wrapper = await mountPicker();
        try {
            const input = wrapper.get<HTMLElement>('[contenteditable]');
            input.element.innerText = '@';
            await input.trigger('input');
            expect(wrapper.get('[role=status]').text()).toContain('Loading your Teams');
            stubs.store.teams = [team];
            stubs.store.library = [
                { id: 'active', profile: { lifecycle: 'active' } },
                { id: 'draft', profile: { lifecycle: 'draft' } },
            ];
            release?.();
            await flushPromises();
            expect(wrapper.get('[role=option]').text()).toContain('1 subagent');
            expect(wrapper.get('[role=option]').attributes('aria-selected')).toBe('true');
            expect(wrapper.find('[role=status]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });
    it('offers retry after a load failure without discarding the query', async () => {
        stubs.store.loadLibrary
            .mockRejectedValueOnce(new Error('Unavailable'))
            .mockImplementationOnce(async () => {
                stubs.store.teams = [team];
            });
        const wrapper = await mountPicker();
        try {
            const input = wrapper.get<HTMLElement>('[contenteditable]');
            input.element.innerText = '@def';
            await input.trigger('input');
            await flushPromises();
            expect(wrapper.get('[role=alert]').text()).toContain('Could not load');
            await wrapper.get('[role=alert] button').trigger('click');
            await flushPromises();
            expect(wrapper.get('[role=option]').text()).toContain('@default');
            expect(input.element.innerText).toBe('@def');
            expect(stubs.store.loadLibrary).toHaveBeenCalledTimes(2);
            await input.trigger('keydown', { key: 'Tab' });
            expect(wrapper.emitted('chosen')).toEqual([['@default ']]);
        } finally {
            wrapper.unmount();
        }
    });
    it('ignores non-leading mentions and leaves unknown queries available for validation', async () => {
        stubs.store.teams = [team];
        const wrapper = await mountPicker();
        try {
            const input = wrapper.get<HTMLElement>('[contenteditable]');
            input.element.innerText = 'Contact person@example.com';
            await input.trigger('input');
            expect(wrapper.find('[role=listbox]').exists()).toBe(false);
            expect(stubs.store.loadLibrary).not.toHaveBeenCalled();
            input.element.innerText = '@unknown';
            await input.trigger('input');
            expect(wrapper.text()).toContain('No Teams match @unknown');
            await input.trigger('keydown', { key: 'Enter' });
            expect(wrapper.emitted('chosen')).toBeUndefined();
            expect(input.element.innerText).toBe('@unknown');
        } finally {
            wrapper.unmount();
        }
    });
});
