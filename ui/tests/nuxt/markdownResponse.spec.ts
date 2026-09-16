import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import MarkdownResponse from '@/components/ui/chat/markdownResponse.vue';
import type { RenderedMarkdownSegment } from '@/composables/useMarkdownProcessor';
import { prepareMarkdownResponse } from '@/utils/markdownResponseTokens';

const createSegment = (html: string): RenderedMarkdownSegment => {
    const prepared = prepareMarkdownResponse(html, 'response-test');
    return Object.freeze({
        id: 'response-1',
        renderKey: 'response-1:0',
        channel: 'response',
        start: 0,
        end: html.length,
        source: html,
        state: 'sealed',
        html: prepared.html,
        tokens: prepared.tokens,
        parserContextFingerprint: '',
        enhancementFingerprint: html,
        revision: 0,
    });
};

describe('MarkdownResponse', () => {
    it('expands only the selected rendered table and keeps its snapshot through streaming replacement', async () => {
        const segment = createSegment('<table><tr><td><strong>First</strong></td></tr></table><table><tr><td><code>&lt;b&gt;Second&lt;/b&gt;</code></td></tr></table>');
        const wrapper = mount(MarkdownResponse, {
            attachTo: document.body,
            props: { segments: [segment], renderMermaidCharts: vi.fn() },
            global: {
                stubs: {
                    UiIcon: true,
                    Dialog: { props: ['open'], template: '<div v-if="open" role="dialog"><slot /></div>' },
                    DialogPanel: { template: '<div><slot /></div>' },
                    DialogTitle: { template: '<h2><slot /></h2>' },
                },
            },
        });
        try {
            const original = wrapper.findAll('table')[1]!.element;
            await wrapper.findAll('button[aria-label="Expand table"]')[1]!.trigger('click');
            const dialog = wrapper.get('[role="dialog"]');
            expect(dialog.text()).toContain('<b>Second</b>');
            expect(dialog.find('b').exists()).toBe(false);
            expect(dialog.find('table').element).not.toBe(original);
            expect(original.isConnected).toBe(true);
            const next = { ...createSegment('<table><tr><td>Updated</td></tr></table>'), renderKey: 'response-1:1' };
            await wrapper.setProps({ segments: [next] });
            expect(wrapper.findAll('button[aria-label="Expand table"]')).toHaveLength(1);
            expect(dialog.text()).toContain('<b>Second</b>');
            await wrapper.get('button[aria-label="Close expanded table"]').trigger('click');
            expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
            expect(wrapper.findAll('table')).toHaveLength(1);
        } finally {
            wrapper.unmount();
        }
    });

    it('renders token components through Vue-owned deferred Teleports', () => {
        const segment = createSegment(
            '<div class="sandbox-download-placeholder" data-file-id="file-1" data-label="Report" data-filename="report.txt"></div>',
        );
        const wrapper = mount(MarkdownResponse, {
            attachTo: document.body,
            props: { segments: [segment], renderMermaidCharts: vi.fn() },
            global: {
                stubs: {
                    SandboxArtifactDownload: {
                        props: ['fileId', 'label'],
                        template: '<button data-testid="download-token">{{ label }}</button>',
                    },
                },
            },
        });

        try {
            expect(wrapper.get('[data-testid="download-token"]').text()).toBe('Report');
        } finally {
            wrapper.unmount();
        }
        expect(document.querySelector('[data-testid="download-token"]')).toBeNull();
    });

    it('defers Mermaid and creates fullscreen state only after finalization', async () => {
        const segment = createSegment('<pre class="mermaid">graph TD; A--&gt;B;</pre>');
        const renderMermaidCharts = vi.fn(async () => undefined);
        const wrapper = mount(MarkdownResponse, {
            attachTo: document.body,
            props: { segments: [segment], renderMermaidCharts },
            global: { stubs: { FullScreenButton: { template: '<button data-testid="fullscreen" />' } } },
        });

        try {
            expect(wrapper.find('[data-testid="fullscreen"]').exists()).toBe(false);
            const finalizePendingMermaid = wrapper.vm.$.exposed?.finalizePendingMermaid;
            if (!isRuntimeFunction(finalizePendingMermaid)) {
                throw new Error('Markdown response did not expose Mermaid finalization');
            }
            await finalizePendingMermaid();
            expect(renderMermaidCharts).toHaveBeenCalledOnce();
            expect(wrapper.find('[data-testid="fullscreen"]').exists()).toBe(true);
        } finally {
            wrapper.unmount();
        }
    });
});
