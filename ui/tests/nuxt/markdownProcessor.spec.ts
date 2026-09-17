import { describe, expect, it, vi } from 'vitest';
import { useMarkdownProcessor } from '@/composables/useMarkdownProcessor';

interface Deferred<T> {
    promise: Promise<T>;
    resolve: (value: T | PromiseLike<T>) => void;
    reject: (reason?: RuntimeValue) => void;
}

const deferred = <T>(): Deferred<T> => {
    let resolve!: Deferred<T>['resolve'];
    let reject!: Deferred<T>['reject'];
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
};

describe('useMarkdownProcessor processMarkdown', () => {
    it('runs tool preprocessing on cleaned text exactly once, without filtering newly adjacent prose', async () => {
        const processor = useMarkdownProcessor();
        const parser = (markdown: string) => Promise.resolve(markdown);
        const preprocessCleanedMarkdown = vi.fn((markdown: string) => markdown);
        const input = 'Before <tool_call_context<tool_call_context>PRIVATE</tool_call_context>> After';
        await processor.processMarkdown(input, parser, undefined, { preprocessCleanedMarkdown });
        expect(preprocessCleanedMarkdown).toHaveBeenCalledExactlyOnceWith('Before <tool_call_context> After');
        expect(processor.responseHtml.value).toBe('Before <tool_call_context> After');
        await processor.processMarkdown('', parser, undefined, { preprocessCleanedMarkdown });
        expect(preprocessCleanedMarkdown).toHaveBeenLastCalledWith('');
        expect(processor.responseHtml.value).toBe('');
    });

    it('filters every streaming prefix before parsing either channel without mutating input', async () => {
        const processor = useMarkdownProcessor();
        const parser = vi.fn((markdown: string) => Promise.resolve(markdown));
        const before = '[THINK]Visible thought';
        const hidden = '<tool_call_context id="old">[ERROR]PRIVATE[!ERROR]<search_query>PRIVATE</search_query></tool_call_context>';
        const after = ' continues[!THINK]\n\n**Visible answer**';
        const input = { text: `${before}${hidden}${after}` };
        const original = input.text;
        for (let end = before.length; end <= input.text.length; end += 1) {
            await processor.processMarkdown(input.text.slice(0, end), parser, undefined, {
                cacheKey: 'legacy-stream', isStreaming: true,
            });
            expect(processor.isError.value).toBe(false);
            expect(processor.webSearches.value).toEqual([]);
            expect(processor.thinkingHtml.value).not.toMatch(/PRIVATE|tool_call_context/);
            expect(processor.responseHtml.value).not.toMatch(/PRIVATE|tool_call_context/);
        }
        const incremental = [processor.thinkingHtml.value, processor.responseHtml.value];
        await processor.processMarkdown(input.text, parser, undefined, {
            cacheKey: 'legacy-stream', isStreaming: false,
        });
        expect([processor.thinkingHtml.value, processor.responseHtml.value]).toEqual(incremental);
        expect(processor.thinkingHtml.value).toBe('Visible thought continues');
        expect(processor.responseHtml.value).toBe('**Visible answer**');
        expect(parser.mock.calls.flat().join('')).not.toContain('PRIVATE');
        expect(input.text).toBe(original);
    });

    it.each(['<', '<tool_call_con', '<tool_call_context'])('restores %s when streaming stops with unchanged input', async (tail) => {
        const processor = useMarkdownProcessor();
        const parser = (markdown: string) => Promise.resolve(markdown);
        const input = `Visible ${tail}`;
        await processor.processMarkdown(input, parser, undefined, { isStreaming: true });
        expect(processor.responseHtml.value).toBe('Visible');
        await processor.processMarkdown(input, parser, undefined, { isStreaming: false });
        expect(processor.responseHtml.value).toBe(input);
    });

    it('keeps a recognized unfinished block hidden on cancellation', async () => {
        const processor = useMarkdownProcessor();
        const parser = (markdown: string) => Promise.resolve(markdown);
        const input = 'Visible <tool_call_context id="old">PRIVATE';
        await processor.processMarkdown(input, parser, undefined, { isStreaming: true });
        await processor.processMarkdown(input, parser, undefined, { isStreaming: false });
        expect(processor.responseHtml.value).toBe('Visible');
    });

    it('does not let an older successful parse overwrite the newest response', async () => {
        const older = deferred<string>();
        const parser = vi.fn((markdown: string) =>
            markdown === 'Older response'
                ? older.promise
                : Promise.resolve('<p>Newest response</p>'),
        );
        const processor = useMarkdownProcessor();

        const olderProcess = processor.processMarkdown('Older response', parser);
        await processor.processMarkdown('Newest response', parser);
        expect(processor.responseHtml.value).toBe('<p>Newest response</p>');

        older.resolve('<p>Older response</p>');
        await olderProcess;

        expect(processor.responseHtml.value).toBe('<p>Newest response</p>');
    });

    it('does not let an older rejected parse overwrite the newest response', async () => {
        const older = deferred<string>();
        const parser = vi.fn((markdown: string) =>
            markdown === 'Older response'
                ? older.promise
                : Promise.resolve('<p>Newest response</p>'),
        );
        const processor = useMarkdownProcessor();
        const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

        try {
            const olderProcess = processor.processMarkdown('Older response', parser);
            await processor.processMarkdown('Newest response', parser);
            expect(processor.responseHtml.value).toBe('<p>Newest response</p>');

            older.reject(new Error('Older parse failed'));
            await olderProcess;

            expect(consoleError).toHaveBeenCalledWith(
                '[useMarkdownProcessor] Parsing failed:',
                expect.any(Error),
            );
            expect(processor.responseHtml.value).toBe('<p>Newest response</p>');
        } finally {
            consoleError.mockRestore();
        }
    });

    it('reuses sealed prefix objects and parses only the changed streaming tail', async () => {
        const parser = vi.fn((markdown: string) => Promise.resolve(`<p>${markdown}</p>`));
        const processor = useMarkdownProcessor();

        await processor.processMarkdown('First block.\n\nSecond', parser, undefined, {
            cacheKey: 'message-1',
            isStreaming: true,
        });
        const firstPrefix = processor.responseSegments.value[0];
        parser.mockClear();

        const result = await processor.processMarkdown('First block.\n\nSecond grows', parser, undefined, {
            cacheKey: 'message-1',
            isStreaming: true,
        });

        expect(processor.responseSegments.value[0]).toBe(firstPrefix);
        expect(result.parsedSegmentCount).toBe(1);
        expect(result.reusedSegmentCount).toBe(1);
        expect(parser).toHaveBeenCalledTimes(1);
    });

    it('seals an unchanged final tail without parsing it again', async () => {
        const parser = vi.fn((markdown: string) => Promise.resolve(`<p>${markdown}</p>`));
        const processor = useMarkdownProcessor();
        await processor.processMarkdown('First block.\n\nStreaming tail', parser, undefined, {
            cacheKey: 'message-1',
            isStreaming: true,
        });
        const activeKey = processor.responseSegments.value.at(-1)?.renderKey;
        const activeTokens = processor.responseSegments.value.at(-1)?.tokens;
        parser.mockClear();

        const result = await processor.processMarkdown('First block.\n\nStreaming tail', parser, undefined, {
            cacheKey: 'message-1',
            isStreaming: false,
        });

        expect(result.parsedSegmentCount).toBe(0);
        expect(parser).not.toHaveBeenCalled();
        expect(processor.responseSegments.value.at(-1)?.renderKey).toBe(activeKey);
        expect(processor.responseSegments.value.at(-1)?.state).toBe('sealed');
        expect(processor.responseSegments.value.at(-1)?.tokens).toBe(activeTokens);
    });

    it('prepares only newly parsed response segments and prepares active fallback output', async () => {
        const parser = vi.fn((markdown: string) => Promise.resolve(`<p>${markdown}</p>`));
        const prepare = vi.fn((html: string) => ({ html: `<main>${html}</main>`, tokens: [] }));
        const processor = useMarkdownProcessor();

        await processor.processMarkdown('Stable.\n\nTail', parser, undefined, {
            cacheKey: 'prepared-message',
            isStreaming: true,
            responseHtmlPreparer: prepare,
        });
        prepare.mockClear();
        await processor.processMarkdown('Stable.\n\nTail grows', parser, undefined, {
            cacheKey: 'prepared-message',
            isStreaming: true,
            responseHtmlPreparer: prepare,
        });
        expect(prepare).toHaveBeenCalledOnce();

        const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
        try {
            await processor.processMarkdown(
                'Fallback response',
                () => Promise.reject(new Error('parse failed')),
                undefined,
                { cacheKey: 'fallback', responseHtmlPreparer: prepare },
            );
            expect(processor.responseHtml.value).toContain('<main>Fallback response</main>');
        } finally {
            consoleError.mockRestore();
        }
    });

    it('invalidates a dependent segment when its reference definition changes', async () => {
        const parser = vi.fn((markdown: string) => Promise.resolve(`<p>${markdown}</p>`));
        const processor = useMarkdownProcessor();
        await processor.processMarkdown(
            '[Source][ref]\n\nUnaffected.\n\n[ref]: https://old.example',
            parser,
            undefined,
            { cacheKey: 'message-1' },
        );
        const unaffected = processor.responseSegments.value[1];
        parser.mockClear();

        const result = await processor.processMarkdown(
            '[Source][ref]\n\nUnaffected.\n\n[ref]: https://new.example',
            parser,
            undefined,
            { cacheKey: 'message-1' },
        );

        expect(result.parsedSegmentCount).toBe(2);
        expect(processor.responseSegments.value[1]).toBe(unaffected);
    });
});
