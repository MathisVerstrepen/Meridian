// --- Composables ---
const { getExecutionPlan } = useAPI();
const graphEvents = useGraphEvents();
const nodeRegistry = useNodeRegistry();

const setExecutionPlan = async (
    graphId: string,
    nodeId: string,
    direction: 'upstream' | 'downstream' | 'all' | 'self',
) => {
    const { error } = useToast();

    try {
        if (direction === 'self') {
            await nodeRegistry.execute(nodeId);
            return;
        }

        const planRes = await getExecutionPlan(graphId, nodeId, direction);
        if (!planRes) {
            error('Failed to get execution plan', { title: 'API Error' });
            return;
        }

        graphEvents.emit('execution-plan', {
            graphId,
            nodeId,
            direction,
            plan: planRes,
        });
    } catch (err) {
        error('Failed to get execution plan', { title: 'API Error' });
    }
};

export const useExecutionPlan = () => {
    return { setExecutionPlan };
};
