import { Marked } from 'marked';
import { isRuntimeString, isRuntimeUndefined } from '@/utils/runtimeTypes';

// A map to store pending promises, keyed by a unique request ID.
const pendingPromises = new Map<
    string,
    {
        resolve: (html: string) => void;
        reject: (err: Error) => void;
    }
>();

let worker: Worker | null = null;
let isInitializing = false;

// Main-thread Marked instance for simple markdown (no code blocks, no math).
// Avoids worker round-trip overhead for the common case.
const mainThreadMarked = new Marked({
    gfm: true,
    breaks: false,
    pedantic: false,
});

/**
 * A composable that provides a singleton interface to the Marked Web Worker.
 */
export const useMarkedWorker = () => {
    // Initialize worker only once
    if (!worker && !isInitializing && !isRuntimeUndefined(window)) {
        isInitializing = true;

        // The `new URL(...)` is crucial for Vite/Nuxt to correctly bundle and locate the worker script.
        worker = new Worker(new URL('~/assets/worker/marked.worker.ts', import.meta.url), {
            type: 'module',
        });

        worker.onmessage = (event: MessageEvent<{ id: string; html?: string; error?: string }>) => {
            const { id, html, error } = event.data;
            const promise = pendingPromises.get(id);

            if (promise) {
                if (error) {
                    promise.reject(new Error(error));
                } else if (isRuntimeString(html)) {
                    promise.resolve(html);
                }
                pendingPromises.delete(id); // Clean up
            }
        };

        worker.onerror = (err) => {
            const { error } = useToast();

            console.error('[Main] Uncaught error in Marked worker:', err);
            error('Failed to initialize Marked worker: ' + err.message, {
                title: 'Worker Error',
            });
            isInitializing = false;
        };
    }

    /**
     * Parses a Markdown string.
     * Simple markdown (no fenced code blocks, no LaTeX) is parsed synchronously
     * on the main thread. Complex markdown is offloaded to the Web Worker.
     */
    const parse = (markdown: string): Promise<string> => {
        const needsWorker = markdown.includes('```') || markdown.includes('$');

        if (!needsWorker) {
            const parsedHtml = mainThreadMarked.parse(markdown);
            if (!isRuntimeString(parsedHtml)) {
                return Promise.reject(
                    new TypeError('Synchronous Markdown parser returned a non-string result'),
                );
            }
            return Promise.resolve(parsedHtml);
        }

        if (!worker) {
            return Promise.reject(
                new Error('Marked worker is not available or failed to initialize.'),
            );
        }

        const activeWorker = worker;
        return new Promise((resolve, reject) => {
            const id = crypto.randomUUID();
            pendingPromises.set(id, { resolve, reject });
            activeWorker.postMessage({ id, markdown });
        });
    };

    return {
        parse,
    };
};
