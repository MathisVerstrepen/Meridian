import { describe, expect, it, vi } from 'vitest';
import { useMarkdownProcessor } from '@/composables/useMarkdownProcessor';

interface Deferred<T> {
    promise: Promise<T>;
    resolve: (value: T | PromiseLike<T>) => void;
    reject: (reason?: unknown) => void;
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
