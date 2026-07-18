import { describe, expect, it } from 'vitest';
import { parseAssistantContent } from '@/utils/markdownParsing';

describe('parseAssistantContent', () => {
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
