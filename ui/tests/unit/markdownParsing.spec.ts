import { describe, expect, it } from 'vitest';
import { parseAssistantContent } from '@/utils/markdownParsing';

describe('parseAssistantContent', () => {
    it('removes legacy payload before errors, thinking, search, fetch and auto-tool extraction', () => {
        const hidden = `<tool_call_context id="old">
[ERROR]hidden error[!ERROR]
[THINK]hidden thought[!THINK]
<section data-auto-tool-selection="web_search"></section>
[WEB_SEARCH]<search_query id="hidden">hidden query</search_query>[!WEB_SEARCH]
<fetch_url id="hidden">Reading content from: https://hidden.example</fetch_url>
</tool_call_context>`;
        const result = parseAssistantContent(`Before ${hidden} middle
[THINK]Visible thought ${hidden} continues[!THINK]
<search_query id="real">real query</search_query>
<fetch_url id="real-fetch">Reading content from: https://example.com</fetch_url>
**After** [source](https://example.com)`);
        expect(result.errorText).toBeNull();
        expect(result.autoToolSelection).toBeNull();
        expect(result.thinkingMarkdown).toBe('Visible thought  continues');
        expect(result.responseMarkdown).toContain('Before  middle');
        expect(result.responseMarkdown).toContain('**After** [source](https://example.com)');
        expect(result.webSearches.map((search) => search.toolCallId)).toEqual(['real']);
        expect(result.fetchedPages.map((page) => page.toolCallId)).toEqual(['real-fetch']);
        expect(JSON.stringify(result)).not.toContain('hidden');
    });

    it('handles unchanged input finalization and does not trim away a recognized boundary', () => {
        expect(parseAssistantContent('Answer <tool_call_context', true).responseMarkdown).toBe('Answer');
        expect(parseAssistantContent('Answer <tool_call_context').responseMarkdown)
            .toBe('Answer <tool_call_context');
        expect(parseAssistantContent('Answer <tool_call_context ').responseMarkdown).toBe('Answer');
        expect(parseAssistantContent('Answer <tool_call_context>hidden').responseMarkdown).toBe('Answer');
    });

    it('collects multiple thoughts and rejoins a visible link interrupted by THINK blocks', () => {
        const result = parseAssistantContent(`
Visible [diagram](visualise://artifact
[THINK] First thought [!THINK]
) remains visible.
[THINK] Second thought [!THINK]
Final answer.
        `);

        expect(result.thinkingMarkdown).toBe('First thought\n\nSecond thought');
        expect(result.responseMarkdown).toBe(
            'Visible [diagram](visualise://artifact\n\n) remains visible.\nFinal answer.',
        );
        expect(result.errorText).toBeNull();
        expect(result.webSearches).toEqual([]);
        expect(result.fetchedPages).toEqual([]);
    });

    it('recovers an unclosed THINK tail after stripping a leading asking-user replay block', () => {
        const result = parseAssistantContent(`
[THINK]
Pre-tool thinking.
<asking_user id="question-1">Which option?</asking_user>
Final answer:
- First
- Second
        `);

        expect(result.thinkingMarkdown).toBe('Pre-tool thinking.');
        expect(result.responseMarkdown).toBe('Final answer:\n- First\n- Second');
    });

    it('removes an open web-search block and marks only its final parsed entry streaming', () => {
        const result = parseAssistantContent(`
[WEB_SEARCH]
<search_query id="search-1">"first query"</search_query>
<search_query id="search-2">second query</search_query>
        `);

        expect(result.responseMarkdown).toBe('');
        expect(result.webSearches).toEqual([
            {
                query: 'first query',
                toolCallId: 'search-1',
                results: [],
                streaming: false,
                error: undefined,
            },
            {
                query: 'second query',
                toolCallId: 'search-2',
                results: [],
                streaming: true,
                error: undefined,
            },
        ]);
    });

    it('short-circuits all other parsing when an error marker is present', () => {
        const result = parseAssistantContent(`
<section data-auto-tool-selection="web_search"></section>
[THINK]Hidden thought[!THINK]
[WEB_SEARCH]<search_query>hidden query</search_query>[!WEB_SEARCH]
[ERROR]  Render failed.  [!ERROR]
Visible response.
        `);

        expect(result).toEqual({
            errorText: 'Render failed.',
            autoToolSelection: null,
            thinkingMarkdown: '',
            responseMarkdown: '',
            webSearches: [],
            fetchedPages: [],
        });
    });
});
