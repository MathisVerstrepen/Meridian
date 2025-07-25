type NodeExecutor = () => Promise<unknown>;

class NodeRegistry {
    private executors: Map<string, NodeExecutor> = new Map();
    
    register(nodeId: string, executor: NodeExecutor) {
        this.executors.set(nodeId, executor);
    }
    
    unregister(nodeId: string) {
        this.executors.delete(nodeId);
    }
    
    async execute(nodeId: string): Promise<unknown> {
        const executor = this.executors.get(nodeId);
        if (executor) {
            return await executor();
        }
        throw new Error(`No executor registered for node ${nodeId}`);
    }
    
    has(nodeId: string): boolean {
        return this.executors.has(nodeId);
    }
}

export const nodeRegistry = new NodeRegistry();

export function useNodeRegistry() {
    return nodeRegistry;
}
