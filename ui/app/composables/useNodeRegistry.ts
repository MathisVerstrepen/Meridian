type NodeExecutor = () => Promise<unknown>;
type NodeStopper = () => Promise<void>;

interface NodeControls {
    execute: NodeExecutor;
    stop: NodeStopper;
    streamSession: Ref<StreamSession | null>;
}

class NodeRegistry {
    private controls: Map<string, NodeControls> = new Map();

    register(
        nodeId: string,
        execute: NodeExecutor,
        stop: NodeStopper,
        streamSession: Ref<StreamSession | null>,
    ) {
        this.controls.set(nodeId, { execute, stop, streamSession });
    }

    unregister(nodeId: string) {
        this.controls.delete(nodeId);
    }

    async execute(nodeId: string): Promise<unknown> {
        const controls = this.controls.get(nodeId);
        if (controls) {
            await controls.execute();

            await new Promise<void>((resolve) => {
                const checkInterval = setInterval(() => {
                    if (!controls.streamSession.value?.isStreaming) {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
            });

            return;
        }
        throw new Error(`No executor registered for node ${nodeId}`);
    }

    async stop(nodeId: string): Promise<void> {
        const controls = this.controls.get(nodeId);
        if (controls) {
            return await controls.stop();
        }
        throw new Error(`No stopper registered for node ${nodeId}`);
    }

    has(nodeId: string): boolean {
        return this.controls.has(nodeId);
    }
}

export const nodeRegistry = new NodeRegistry();

export function useNodeRegistry() {
    return nodeRegistry;
}
