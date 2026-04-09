import type { ToolCallDetail } from '@/types/toolCall';

const toolCallDetailCache = reactive(new Map<string, ToolCallDetail>());
const pendingToolCallRequests = new Map<string, Promise<ToolCallDetail>>();

export const useToolCallDetails = () => {
    const { getToolCallDetail } = useAPI();

    const fetchToolCallDetail = async (
        toolCallId: string,
        forceRefresh: boolean = false,
    ): Promise<ToolCallDetail> => {
        if (forceRefresh) {
            toolCallDetailCache.delete(toolCallId);
            pendingToolCallRequests.delete(toolCallId);
        }

        const cached = toolCallDetailCache.get(toolCallId);
        if (cached) {
            return cached;
        }

        const pending = pendingToolCallRequests.get(toolCallId);
        if (pending) {
            return pending;
        }

        const request = getToolCallDetail(toolCallId)
            .then((detail) => {
                toolCallDetailCache.set(toolCallId, detail);
                pendingToolCallRequests.delete(toolCallId);
                return detail;
            })
            .catch((error) => {
                pendingToolCallRequests.delete(toolCallId);
                throw error;
            });

        pendingToolCallRequests.set(toolCallId, request);
        return request;
    };

    return {
        fetchToolCallDetail,
    };
};
