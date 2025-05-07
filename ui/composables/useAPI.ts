import type { Graph, CompleteGraph, CompleteGraphRequest, Message } from '@/types/graph';
import type { GenerateRequest } from '@/types/chat';
import type { ResponseModel } from '@/types/model';
const { mapEdgeRequestToEdge, mapNodeRequestToNode, mapNodeToNodeRequest, mapEdgeToEdgeRequest } =
    graphMappers();

const API_BASE_URL = 'http://localhost:8000';

export const useAPI = () => {
    /**
     * Creates a configured fetch request using Nuxt's useFetch
     * @param url The API endpoint URL
     * @param options Fetch options
     * @returns Promise with the response data
     */
    const apiFetch = async <T>(url: string, options: any = {}): Promise<T> => {
        try {
            const data = $fetch(url, {
                baseURL: API_BASE_URL,
                ...options,
            });

            return data as T;
        } catch (error) {
            console.error(`Error fetching ${url}:`, error);
            throw error;
        }
    };

    /**
     * Fetches all available graphs from the API.
     */
    const getGraphs = async (): Promise<Graph[]> => {
        return apiFetch<Graph[]>('/graphs', {
            method: 'GET',
            headers: {
                Accept: 'application/json',
            },
        });
    };

    /**
     * Fetches a complete graph by its ID from the API.
     */
    const getGraphById = async (graphId: string): Promise<CompleteGraph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for getGraphById');
        }

        const data = await apiFetch<CompleteGraphRequest>(`/graph/${graphId}`, {
            method: 'GET',
            headers: {
                Accept: 'application/json',
            },
        });

        const nodes = data.nodes.map(mapNodeRequestToNode);
        const edges = data.edges.map(mapEdgeRequestToEdge);
        return {
            graph: data.graph,
            nodes,
            edges,
        };
    };

    /**
     * Creates a new graph.
     */
    const createGraph = async (): Promise<Graph> => {
        return apiFetch<Graph>('/graph/create', {
            method: 'POST',
            headers: {
                Accept: 'application/json',
            },
        });
    };

    /**
     * Updates an existing graph with the provided data
     */
    const updateGraph = async (graphId: string, saveData: CompleteGraph): Promise<Graph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for updateGraph');
        }

        return apiFetch<Graph>(`/graph/${graphId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            body: {
                graph: saveData.graph,
                nodes: saveData.nodes.map((node) => mapNodeToNodeRequest(node, graphId)),
                edges: saveData.edges.map((edge) => mapEdgeToEdgeRequest(edge, graphId)),
            },
        });
    };

    /**
     * Updates the name of a graph with the given ID
     */
    const updateGraphName = async (graphId: string, graphName: string): Promise<Graph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for updateGraphName');
        }

        return apiFetch<Graph>(`/graph/${graphId}/update-name`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            params: {
                new_name: graphName,
            },
        });
    };

    /**
     * Deletes a graph by its ID.
     */
    const deleteGraph = async (graphId: string): Promise<void> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for deleteGraph');
        }

        await apiFetch<void>(`/graph/${graphId}`, {
            method: 'DELETE',
            headers: {
                Accept: 'application/json',
            },
        });
    };

    /**
     * Fetches chat messages for a specific node in a graph.
     */
    const getChat = async (graphId: string, nodeId: string): Promise<Message[]> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for getChat');
        }
        if (!nodeId) {
            throw new Error('nodeId cannot be empty for getChat');
        }

        return apiFetch<Message[]>(`/chat/${graphId}/${nodeId}`, {
            method: 'GET',
            headers: {
                Accept: 'application/json',
            },
        });
    };

    /**
     * Fetches a stream of generated text from the API.
     * Note: useFetch doesn't support streaming, so we keep the original fetch implementation
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
            console.error('Failed to fetch stream:', error);
        }
    };

    /**
     * Fetches available models from the OpenRouter API.
     */
    const getOpenRouterModels = async (): Promise<ResponseModel> => {
        return apiFetch<ResponseModel>('/models', {
            method: 'GET',
            headers: {
                Accept: 'application/json',
            },
        });
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
        getOpenRouterModels,
    };
};
