export const useGraphRenderReady = (graphId: ComputedRef<string>) => {
    const waitForRender = async () => {
        const { areNodesInitialized, onNodesInitialized } = useGraphFlow('main-graph-' + graphId.value);

        // Flush new nodes and their mounted executors before checking current state.
        await nextTick();
        if (areNodesInitialized.value) return;

        await new Promise<void>((resolve) => {
            const finish = () => {
                clearTimeout(timeout);
                unsubscribe.off();
                resolve();
            };
            const unsubscribe = onNodesInitialized(finish);
            // Rendering is best-effort: a hidden canvas may never emit initialization.
            // Continue to execution, which can report a missing executor explicitly.
            const timeout = setTimeout(finish, 1000);
            if (areNodesInitialized.value) finish();
        });
        await nextTick();
    };

    return { waitForRender };
};
