import { describe, expect, it } from 'vitest';
import { prepareMarkdownResponse } from '@/utils/markdownResponseTokens';

describe('prepareMarkdownResponse', () => {
    it('prepares all special nodes and response favicons in one detached document', () => {
        const prepared = prepareMarkdownResponse(
            [
                '<a href="https://example.com/path">External</a>',
                '<div class="generated-image-placeholder" data-prompt="Prompt &amp; more" data-image-url="/image"></div>',
                '<div class="tool-question-placeholder" data-tool-call-id="question-1"></div>',
                '<div class="sandbox-download-placeholder" data-file-id="file-1" data-label="Report" data-filename="report.txt"></div>',
                '<div class="sandbox-html-placeholder" data-file-id="html-1" data-title="Result" data-filename="result.html"></div>',
                '<div class="visualise-artifact-placeholder" data-file-id="visual-1" data-caption="Chart"></div>',
                '<pre><pre class="replace-code-containers">const value = 1;</pre></pre>',
                '<pre class="mermaid">graph TD; A--&gt;B;</pre>',
            ].join(''),
            'scope-1',
        );

        expect(prepared.tokens.map((token) => token.kind)).toEqual([
            'generated-image',
            'tool-question',
            'sandbox-download',
            'sandbox-html',
            'visualise',
            'code-copy',
            'mermaid-fullscreen',
        ]);
        expect(prepared.html).toContain('data-external-link-favicon');
        expect(prepared.html).toContain('code-wrapper relative');
        expect(prepared.html).toContain('mermaid-wrapper relative');
        expect(prepared.html).not.toContain('generated-image-placeholder');
        expect(Object.isFrozen(prepared.tokens)).toBe(true);
    });

    it('keeps missing-attribute placeholders inert', () => {
        const prepared = prepareMarkdownResponse(
            '<div class="sandbox-download-placeholder" data-file-id="file-1"></div>',
            'scope-2',
        );
        expect(prepared.tokens).toHaveLength(0);
        expect(prepared.html).toContain('sandbox-download-placeholder');
    });
});
