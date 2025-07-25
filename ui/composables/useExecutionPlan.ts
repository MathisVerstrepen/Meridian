// --- Composables ---
const { getExecutionPlan } = useAPI();
const { error } = useToast();
const graphEvents = useGraphEvents();

const setExecutionPlan = async (
    graphId: string,
    nodeId: string,
    direction: 'upstream' | 'self' | 'downstream' | 'all',
) => {
    try {
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
