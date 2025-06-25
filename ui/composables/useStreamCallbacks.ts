export const useStreamCallbacks = () => {
    const { error } = useToast();

    /**
     * Builds a callback function that processes stream chunks.
     * The callback handles special markers for start, end, and usage data,
     * and passes regular data chunks to the provided data callback.
     *
     * @param startCallback - Function to call when a stream starts.
     * @param endCallback - Function to call when a stream ends.
     * @param usageCallback - Function to call with usage data.
     * @param dataCallback - Function to call with regular data chunks.
     * @returns A function that processes incoming stream chunks.
     */
    const addChunkCallbackBuilder = (
        startCallback: () => void,
        endCallback: (() => void) | (() => Promise<void>),
        usageCallback: (usageData: any) => void,
        dataCallback: (chunk: string) => void,
    ) => {
        return async (chunk: string) => {
            if (chunk === '[START]') {
                startCallback();
                return;
            } else if (chunk === '[END]') {
                await endCallback();
                return;
            } else if (chunk.includes('[USAGE]')) {
                try {
                    const usageData = JSON.parse(chunk.slice(7));
                    usageCallback(usageData);
                } catch (err) {
                    console.error('Error parsing usage data:', err);
                    error('Failed to parse usage data: ' + (err as Error).message, {
                        title: 'Stream Error',
                    });
                }
                return;
            }

            dataCallback(chunk);
        };
    };

    /**
     * Builds a callback function that processes stream chunks with an associated model ID.
     * The callback handles special markers for start, end, and usage data,
     * and passes regular data chunks along with the model ID to the provided data callback.
     *
     * @param startCallback - Function to call when a stream starts, with model ID.
     * @param endCallback - Function to call when a stream ends.
     * @param usageCallback - Function to call with usage data and model ID.
     * @param dataCallback - Function to call with regular data chunks and model ID.
     * @returns A function that processes incoming stream chunks with model ID.
     */
    const addChunkCallbackBuilderWithId = (
        startCallback: (modelId: string) => void,
        endCallback: () => void,
        usageCallback: (usageData: any, modelId: string) => void,
        dataCallback: (chunk: string, modelId: string) => void,
    ) => {
        return (chunk: string, modelId: string) => {
            if (chunk === '[START]') {
                startCallback(modelId);
                return;
            } else if (chunk === '[END]') {
                endCallback();
                return;
            } else if (chunk.includes('[USAGE]')) {
                try {
                    const usageData = JSON.parse(chunk.slice(7));
                    usageCallback(usageData, modelId);
                } catch (err) {
                    console.error('Error parsing usage data:', err);
                    error('Failed to parse usage data: ' + (err as Error).message, {
                        title: 'Stream Error',
                    });
                }
                return;
            }

            dataCallback(chunk, modelId);
        };
    };

    return {
        addChunkCallbackBuilder,
        addChunkCallbackBuilderWithId,
    };
};
