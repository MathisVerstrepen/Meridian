import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, h, nextTick, type PropType } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Activity from '@/components/ui/library/agent/activity.vue';
import ExecutionSummary from '@/components/ui/library/agent/executionSummary.vue';
import { useAgentStore } from '@/stores/agent';
import type { AgentRun } from '@/types/agent';
import type { Message } from '@/types/graph';
import { isJsonObject } from '@/utils/runtimeTypes';

mockNuxtImport('useAPI', () => () => ({ apiFetch: vi.fn() }));
const Markdown = defineComponent({
    // SAFETY: Activity passes the Message-shaped value from runMessage to this renderer stub.
    props: { message: { type: Object as PropType<Message>, required: true } },
    setup: (props) => () =>
        h('div', props.message.content.map((part) => ('text' in part ? part.text : '')).join('')),
});
const run = (id: string, parentId: string | null): AgentRun => ({
    id,
    parent_id: parentId,
    agent_id: parentId ? 'profile-id' : null,
    name: parentId ? 'Researcher' : 'Main model',
    handle: 'researcher',
    version: parentId ? 2 : null,
    instructions: 'Find sources',
    status: 'completed',
    result: parentId ? 'Subagent evidence' : 'Root answer',
    error: null,
    tool_calls: [],
});
const mountActivity = (runs: Record<string, AgentRun>) => {
    const execution: unknown = JSON.parse(JSON.stringify({ runs }));
    if (!isJsonObject(execution)) throw new Error('Invalid execution fixture');
    return mountSuspended(Activity, {
        props: { nodeId: 'node', execution },
        global: { stubs: { UiChatMarkdownRenderer: Markdown, UiChatUtilsToolQuestionCard: true } },
    });
};

describe('subagent chat activity', () => {
    beforeEach(() => setActivePinia(createPinia()));

    it('omits all main-model metadata and its duplicate reply', async () => {
        const wrapper = await mountActivity({ main: run('main', null) });
        try {
            expect(wrapper.find('[aria-label="Subagent activity"]').exists()).toBe(false);
            expect(wrapper.text()).not.toContain('Root answer');
        } finally {
            wrapper.unmount();
        }
    });

    it('renders historical subagents as independent, accessible disclosures', async () => {
        const wrapper = await mountActivity({
            main: run('main', null),
            first: {
                ...run('first', 'main'),
                tool_calls: [{ id: 'tool-id', name: 'web_search', arguments: {}, result: {} }],
            },
            second: run('second', 'main'),
        });
        try {
            expect(wrapper.find('[data-run-id="main"]').exists()).toBe(false);
            const buttons = wrapper.findAll('[data-testid="subagent-disclosure-button"]');
            expect(buttons).toHaveLength(2);
            expect(buttons[0]!.attributes('aria-expanded')).toBe('false');
            expect(wrapper.text()).not.toContain('Subagent evidence');
            await buttons[0]!.trigger('click');
            expect(buttons[0]!.attributes('aria-expanded')).toBe('true');
            expect(buttons[1]!.attributes('aria-expanded')).toBe('false');
            expect(wrapper.get('[data-run-id="first"]').text()).toContain('Task: Find sources');
            expect(wrapper.get('[data-run-id="first"]').text()).toContain('Version 2');
            expect(wrapper.get('[data-run-id="first"]').text()).toContain('Subagent evidence');
            expect(wrapper.get('[data-run-id="first"]').text()).not.toContain('web_search');
            expect(wrapper.find('[data-run-id="first"] details').exists()).toBe(false);
            await buttons[0]!.trigger('click');
            await nextTick();
            expect(wrapper.emitted('triggerScroll')).toHaveLength(1);
        } finally {
            wrapper.unmount();
        }
    });

    it('keeps an expanded run open during live status changes and exposes errors and paused questions', async () => {
        const wrapper = await mountActivity({});
        const store = useAgentStore(wrapper.vm.$pinia);
        try {
            store.runs.node = { first: { ...run('first', 'main'), status: 'running' } };
            await nextTick();
            const button = wrapper.get('[data-testid="subagent-disclosure-button"]');
            expect(button.text()).toContain('Running');
            await button.trigger('click');
            store.runs.node.first!.status = 'paused';
            store.runs.node.first!.pending_tool_call_id = 'question-id';
            await nextTick();
            expect(button.text()).toContain('Needs your input');
            expect(button.attributes('aria-expanded')).toBe('true');
            expect(wrapper.findComponent({ name: 'UiChatUtilsToolQuestionCard' }).exists()).toBe(
                true,
            );
            store.runs.node.first!.status = 'failed';
            store.runs.node.first!.error = 'Provider unavailable';
            await nextTick();
            expect(button.text()).toContain('Failed');
            expect(wrapper.get('[role="alert"]').text()).toBe('Provider unavailable');
        } finally {
            wrapper.unmount();
        }
    });
});

describe('compact node execution summary', () => {
    beforeEach(() => setActivePinia(createPinia()));

    it('lists each invoked profile once without exposing expandable details or the main model', async () => {
        const execution: unknown = JSON.parse(
            JSON.stringify({
                runs: {
                    main: run('main', null),
                    first: run('first', 'main'),
                    repeated: run('repeated', 'main'),
                    second: { ...run('second', 'main'), agent_id: 'reviewer-id', name: 'Reviewer' },
                },
            }),
        );
        if (!isJsonObject(execution)) throw new Error('Invalid execution fixture');
        const wrapper = await mountSuspended(ExecutionSummary, {
            props: { nodeId: 'summary-node', execution },
            global: { stubs: { UiIcon: true } },
        });
        try {
            expect(wrapper.text()).toBe('Subagents: Researcher, Reviewer');
            expect(wrapper.find('button, summary, details, [aria-expanded]').exists()).toBe(false);
            expect(wrapper.text()).not.toContain('Subagent evidence');
            expect(wrapper.text()).not.toContain('Main model');
        } finally {
            wrapper.unmount();
        }
    });

    it('tracks live invocations and hides the summary when no subagents have run', async () => {
        const wrapper = await mountSuspended(ExecutionSummary, {
            props: { nodeId: 'summary-live-node' },
            global: { stubs: { UiIcon: true } },
        });
        const store = useAgentStore(wrapper.vm.$pinia);
        try {
            expect(wrapper.find('[aria-label="Executed subagents"]').exists()).toBe(false);
            store.runs['summary-live-node'] = {
                main: run('main', null),
                first: { ...run('first', 'main'), status: 'running' },
            };
            await nextTick();
            expect(wrapper.text()).toBe('Subagents: Researcher');
            store.runs['summary-live-node'] = { main: run('new-main', null) };
            await nextTick();
            expect(wrapper.find('[aria-label="Executed subagents"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });
});
