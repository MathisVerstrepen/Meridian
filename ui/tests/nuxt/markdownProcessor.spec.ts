import { ref } from 'vue';
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
        const processor = useMarkdownProcessor(ref<HTMLElement | null>(null));

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
        const processor = useMarkdownProcessor(ref<HTMLElement | null>(null));
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
});
