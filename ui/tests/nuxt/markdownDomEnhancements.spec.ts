import { ref } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useMarkdownDomEnhancements } from '@/composables/useMarkdownDomEnhancements';

describe('useMarkdownDomEnhancements', () => {
    afterEach(() => {
        document.body.replaceChildren();
    });

    it('defers Mermaid while streaming and finalizes only pending segment roots', async () => {
        const container = document.createElement('div');
        container.innerHTML = `
            <div data-markdown-segment-key="response-1:0"><pre class="mermaid">graph TD; A--&gt;B;</pre></div>
            <div data-markdown-segment-key="response-2:0"><pre class="mermaid">graph TD; C--&gt;D;</pre></div>
        `;
        document.body.appendChild(container);
        const renderMermaidCharts = vi.fn((_selector?: string) => Promise.resolve());
        const enhancements = useMarkdownDomEnhancements({
            contentRef: ref(container),
            renderMermaidCharts,
            openLightbox: vi.fn(),
        });

        await enhancements.enhance(['response-1:0'], true);
        expect(renderMermaidCharts).not.toHaveBeenCalled();

        await enhancements.finalizePendingMermaid();
        expect(renderMermaidCharts).toHaveBeenCalledTimes(1);
        expect(renderMermaidCharts.mock.calls[0]?.[0]).toContain('response-1:0');
        expect(renderMermaidCharts.mock.calls[0]?.[0]).not.toContain('response-2:0');
        enhancements.disposeAll();
    });

    it('drops disposed pending Mermaid roots before finalization', async () => {
        const container = document.createElement('div');
        container.innerHTML =
            '<div data-markdown-segment-key="response-1:0"><pre class="mermaid">graph TD; A--&gt;B;</pre></div>';
        document.body.appendChild(container);
        const renderMermaidCharts = vi.fn((_selector?: string) => Promise.resolve());
        const enhancements = useMarkdownDomEnhancements({
            contentRef: ref(container),
            renderMermaidCharts,
            openLightbox: vi.fn(),
        });

        await enhancements.enhance(['response-1:0'], true);
        enhancements.dispose(['response-1:0']);
        await enhancements.finalizePendingMermaid();

        expect(renderMermaidCharts).not.toHaveBeenCalled();
    });
});
