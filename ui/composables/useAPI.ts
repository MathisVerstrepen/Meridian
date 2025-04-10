import type {
    Graph,
    CompleteGraph,
    CompleteGraphRequest,
    Message,
} from '@/types/graph';
import type { GenerateRequest } from '@/types/chat';
const {
    mapEdgeRequestToEdge,
    mapNodeRequestToNode,
    mapNodeToNodeRequest,
    mapEdgeToEdgeRequest,
} = graphMappers();

interface ApiError {
    detail?: string | object;
}

const API_BASE_URL = 'http://localhost:8000';

export const useAPI = () => {
    /**
     * Processes an HTTP response and handles error cases.
     *
     * @template T - The expected return type from the API response
     * @param {Response} response - The fetch Response object to process
     * @returns {Promise<T>} A promise that resolves to the parsed JSON response
     * @throws {Error} If the response is not OK (status outside 200-299 range)
     *
     * @remarks
     * - For non-OK responses, attempts to parse the error data from the response body
     * - For 204 No Content responses, returns undefined
     * - For successful responses with content, parses and returns the JSON body
     */
    const handleResponse = async <T>(response: Response): Promise<T> => {
        if (!response.ok) {
            let errorData: ApiError | string =
                `HTTP error ${response.status}: ${response.statusText}`;
            try {
                const body = await response.json();
                errorData = body || errorData;
            } catch (e) {}
            console.error('API Request Failed:', errorData);
            throw new Error(
                typeof errorData === 'string'
                    ? errorData
                    : JSON.stringify(errorData),
            );
        }
        if (response.status === 204) {
            return undefined as T;
        }
        return response.json() as Promise<T>;
    };

    /**
     * Fetches all available graphs from the API.
     *
     * @returns A promise that resolves to an array of Graph objects.
     * @throws Will throw an error if the API request fails.
     */
    const getGraphs = async (): Promise<Graph[]> => {
        try {
            const response = await fetch(`${API_BASE_URL}/graphs`, {
                method: 'GET',
                headers: {
                    Accept: 'application/json',
                },
            });
            const data = await handleResponse<Graph[]>(response);
            return data;
        } catch (err) {
            throw err;
        }
    };

    /**
     * Fetches a complete graph by its ID from the API.
     *
     * @param graphId - The unique identifier of the graph to retrieve
     * @returns A Promise that resolves to a CompleteGraph object containing the graph data, nodes, and edges
     * @throws Will throw an error if the API request fails or if the response handling fails
     */
    const getGraphById = async (graphId: string): Promise<CompleteGraph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for getGraphById');
        }
        try {
            const response = await fetch(`${API_BASE_URL}/graph/${graphId}`, {
                method: 'GET',
                headers: {
                    Accept: 'application/json',
                },
            });
            const data = await handleResponse<CompleteGraphRequest>(response);
            const nodes = data.nodes.map(mapNodeRequestToNode);
            const edges = data.edges.map(mapEdgeRequestToEdge);
            return {
                graph: data.graph,
                nodes,
                edges,
            };
        } catch (err) {
            throw err;
        }
    };

    /**
     * Creates a new graph by making a POST request to the graph creation endpoint.
     *
     * @async
     * @function createGraph
     * @returns {Promise<Graph>} A promise that resolves to the created Graph object
     * @throws {Error} If the request fails or the response cannot be properly handled
     */
    const createGraph = async (): Promise<Graph> => {
        try {
            const response = await fetch(`${API_BASE_URL}/graph/create`, {
                method: 'POST',
                headers: {
                    Accept: 'application/json',
                },
            });
            const data = await handleResponse<Graph>(response);
            return data;
        } catch (err) {
            throw err;
        }
    };

    /**
     * Updates an existing graph with the provided data
     *
     * @param graphId - The unique identifier of the graph to update
     * @param saveData - The data to update the graph with
     * @returns A promise that resolves to the updated Graph object
     * @throws Error if graphId is empty or if the API request fails
     */
    const updateGraph = async (
        graphId: string,
        saveData: CompleteGraph,
    ): Promise<Graph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for updateGraph');
        }
        try {
            const response = await fetch(
                `${API_BASE_URL}/graph/${graphId}/update`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Accept: 'application/json',
                    },
                    body: JSON.stringify({
                        graph: saveData.graph,
                        nodes: saveData.nodes.map((node) =>
                            mapNodeToNodeRequest(node, graphId),
                        ),
                        edges: saveData.edges.map((edge) =>
                            mapEdgeToEdgeRequest(edge, graphId),
                        ),
                    }),
                },
            );
            const data = await handleResponse<Graph>(response);
            return data;
        } catch (err) {
            throw err;
        }
    };

    /**
     * Updates the name of a graph with the given ID
     *
     * @param graphId - The ID of the graph to update
     * @param graphName - The new name for the graph
     * @returns Promise resolving to the updated Graph object
     * @throws Error if graphId is empty
     */
    const updateGraphName = async (
        graphId: string,
        graphName: string,
    ): Promise<Graph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for updateGraphName');
        }
        try {
            const response = await fetch(
                `${API_BASE_URL}/graph/${graphId}/update-name?` +
                    new URLSearchParams({
                        new_name: graphName,
                    }),
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Accept: 'application/json',
                    },
                },
            );
            const data = await handleResponse<Graph>(response);
            return data;
        } catch (err) {
            throw err;
        }
    };

    /**
     * Deletes a graph by its ID.
     *
     * @param graphId - The ID of the graph to delete
     * @throws {Error} If graphId is empty or falsy
     * @throws {Error} If the API request fails
     * @returns A Promise that resolves when the graph is successfully deleted
     */
    const deleteGraph = async (graphId: string): Promise<void> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for deleteGraph');
        }
        try {
            const response = await fetch(`${API_BASE_URL}/graph/${graphId}`, {
                method: 'DELETE',
                headers: {
                    Accept: 'application/json',
                },
            });
            await handleResponse<void>(response);
        } catch (err) {
            throw err;
        }
    };

    /**
     * Fetches a stream of generated text from the API and processes it chunk by chunk.
     *
     * @param generateRequest - The request object containing parameters for text generation
     * @param chunkCallback - Callback function that is called with each chunk of text as it arrives
     * @returns A Promise that resolves when the stream has been fully processed
     * @throws Error if the API returns a non-OK response or if the response body is missing
     *
     * @example
     * ```typescript
     * await getGenerateStream(
     *   { ... },
     *   (chunk) => {
     *     console.log("Received chunk:", chunk);
     *   }
     * );
     * ```
     */
    const getGenerateStream = async (
        generateRequest: GenerateRequest,
        chunkCallback: ((chunk: string) => void) | ((chunk: string) => void)[],
    ) => {
        try {
            const response = await fetch(`${API_BASE_URL}/chat/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'text/plain',
                },
                body: JSON.stringify(generateRequest),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(
                    `API Error: ${response.status} ${response.statusText}. ${errorText || ''}`,
                );
            }

            if (!response.body) {
                throw new Error('Response body is missing');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            if (Array.isArray(chunkCallback)) {
                chunkCallback.forEach((callback) => callback('[START]'));
            } else {
                chunkCallback('[START]');
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    break;
                }
                const chunk = decoder.decode(value, { stream: true });

                if (Array.isArray(chunkCallback)) {
                    chunkCallback.forEach((callback) => callback(chunk));
                } else {
                    chunkCallback(chunk);
                }
            }
        } catch (error) {
            // TODO: Handle error
            console.error('Failed to fetch stream:', error);
        }
    };

    /**
     * Fetches chat messages for a specific node in a graph.
     * @param graphId - The ID of the graph containing the chat.
     * @param nodeId - The ID of the node for which to retrieve chat messages.
     * @returns A promise that resolves to an array of Message objects.
     * @throws Error if graphId or nodeId is empty.
     * @throws Error if the fetch request fails or returns an invalid response.
     */
    const getChat = async (graphId: string, nodeId: string) => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for getChat');
        }
        if (!nodeId) {
            throw new Error('nodeId cannot be empty for getChat');
        }
        try {
            const response = await fetch(
                `${API_BASE_URL}/chat/${graphId}/${nodeId}`,
                {
                    method: 'GET',
                    headers: {
                        Accept: 'application/json',
                    },
                },
            );
            const data = await handleResponse<Message[]>(response);
            return data;
        } catch (err) {
            throw err;
        }
    };

    return {
        getGraphs,
        getGraphById,
        createGraph,
        updateGraph,
        deleteGraph,
        updateGraphName,
        getGenerateStream,
        getChat,
    };
};
