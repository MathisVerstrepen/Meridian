import { afterEach, describe, expect, it, vi } from 'vitest';

type MarkedWorkerRequest = {
    id: string;
    markdown: string;
};

type MarkedWorkerHandler = (event: MessageEvent<MarkedWorkerRequest>) => Promise<void>;

interface MarkedWorkerScope {
    onmessage: MarkedWorkerHandler | null;
    postMessage: ReturnType<typeof vi.fn>;
}

describe('marked worker entry', () => {
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('renders highlighted markdown with runtime helpers bound inside worker scope', async () => {
        const postMessage = vi.fn();
        const workerScope: MarkedWorkerScope = {
            onmessage: null,
            postMessage,
        };
        vi.stubGlobal('self', workerScope);

        await import('@/assets/worker/marked.worker');

        expect(workerScope.onmessage).not.toBeNull();
        await workerScope.onmessage!(new MessageEvent<MarkedWorkerRequest>('message', {
            data: {
                id: 'request-1',
                markdown: '```typescript\nconst answer = 42;\n```',
            },
        }));

        expect(postMessage).toHaveBeenCalledOnce();
        expect(postMessage).toHaveBeenCalledWith({
            id: 'request-1',
            html: expect.stringContaining('not-prose'),
        });
    });
});
