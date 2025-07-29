import { ExecutionPlanDirectionEnum } from '@/types/enums';

// --- Composables ---
const { getExecutionPlan } = useAPI();
const graphEvents = useGraphEvents();
const nodeRegistry = useNodeRegistry();

const setExecutionPlan = async (
    graphId: string,
    nodeId: string,
    direction: ExecutionPlanDirectionEnum,
) => {
    const { error } = useToast();

    try {
        if (direction === ExecutionPlanDirectionEnum.SELF) {
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
