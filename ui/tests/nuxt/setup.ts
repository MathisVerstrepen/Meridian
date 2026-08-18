import { afterAll, vi } from 'vitest';

class WorkerStub extends EventTarget {
    onerror: ((this: Worker, event: ErrorEvent) => void) | null = null;
    onmessage: ((this: Worker, event: MessageEvent) => void) | null = null;
    onmessageerror: ((this: Worker, event: MessageEvent) => void) | null = null;

    postMessage(_message: RuntimeValue, _optionsOrTransfer?: StructuredSerializeOptions | Transferable[]) {}

    terminate() {}
}

vi.stubGlobal('Worker', WorkerStub);

afterAll(() => {
    vi.unstubAllGlobals();
});
