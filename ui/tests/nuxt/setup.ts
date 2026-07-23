import { afterAll, vi } from 'vitest';

class WorkerStub extends EventTarget {
    onerror: ((this: Worker, event: ErrorEvent) => unknown) | null = null;
    onmessage: ((this: Worker, event: MessageEvent) => unknown) | null = null;
    onmessageerror: ((this: Worker, event: MessageEvent) => unknown) | null = null;

    postMessage(_message: unknown, _optionsOrTransfer?: StructuredSerializeOptions | Transferable[]) {}

    terminate() {}
}

vi.stubGlobal('Worker', WorkerStub);

afterAll(() => {
    vi.unstubAllGlobals();
});
