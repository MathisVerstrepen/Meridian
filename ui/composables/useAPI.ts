import type { Graph, CompleteGraph, CompleteGraphRequest, Message } from '@/types/graph';
import type { GenerateRequest } from '@/types/chat';
import type { Settings } from '@/types/settings';
import type { ResponseModel } from '@/types/model';
import type { User } from '@/types/user';

const { mapEdgeRequestToEdge, mapNodeRequestToNode } = graphMappers();

export const useAPI = () => {
    const { error } = useToast();

    /**
     * Creates a configured fetch request using Nuxt's useFetch
     * @param url The API endpoint URL
     * @param options Fetch options
     * @returns Promise with the response data
     */
    const apiFetch = async <T>(url: string, options: any = {}): Promise<T> => {
        const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

        try {
            const data = await $fetch(url, {
                baseURL: API_BASE_URL,
                ...options,
                headers: {
                    ...options.headers,
                    Authorization: `Bearer ${localStorage.getItem('access_token')}`,
                },
            });

            return data as T;
        } catch (err: any) {
            if (err?.response?.status === 401) {
                window.location.href = '/auth/login?error=unauthorized';
                return Promise.reject(err);
            }
            console.error(`Error fetching ${url}:`, err);
            error(`Failed to fetch ${url}`, { title: 'API Error' });
            throw err;
        }
    };

    /**
     * Fetches all available graphs from the API.
     */
    const getGraphs = async (): Promise<Graph[]> => {
        return apiFetch<Graph[]>(`/graphs`, {
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
    const updateGraph = async (
        graphId: string,
        saveData: { graph: any; nodes: any[]; edges: any[] },
    ): Promise<Graph> => {
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
                nodes: saveData.nodes,
                edges: saveData.edges,
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
     * Updates the configuration of a graph with the given ID
     */
    const updateGraphConfig = async (
        graphId: string,
        config: Record<string, any>,
    ): Promise<Graph> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for updateGraphConfig');
        }
        return apiFetch<Graph>(`/graph/${graphId}/update-config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            body: {
                config: config,
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

    const stream = async (
        generateRequest: GenerateRequest,
        getCallbacks: () => ((chunk: string) => Promise<void>)[],
        apiEndpoint: string = '/chat/generate',
    ) => {
        const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

        try {
            await Promise.all(getCallbacks().map((callback) => callback('[START]')));

            const response = await fetch(`${API_BASE_URL}${apiEndpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'text/plain',
                    Authorization: `Bearer ${localStorage.getItem('access_token')}`,
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

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    break;
                }
                const chunk = decoder.decode(value, { stream: true });

                await Promise.all(getCallbacks().map((callback) => callback(chunk)));
            }

            await Promise.all(getCallbacks().map(async (callback) => await callback('[END]')));
        } catch (err) {
            console.error('Failed to fetch stream:', err);
            error(`Failed to fetch stream: ${err}`, { title: 'Stream Error' });
        }
    };

    /**
     * Fetches a stream of generated text from the API.
     * Note: useFetch doesn't support streaming, so we keep the original fetch implementation
     */
    const getGenerateStream = async (
        generateRequest: GenerateRequest,
        getCallbacks: () => ((chunk: string) => Promise<void>)[],
    ) => {
        await stream(generateRequest, getCallbacks, '/chat/generate');
    };

    /**
     * Fetches a stream of generated text from the API for the aggregator of parallelization bloc.
     * Note: useFetch doesn't support streaming, so we keep the original fetch implementation
     */
    const getGenerateParallelizationAggregatorStream = async (
        generateRequest: GenerateRequest,
        getCallbacks: () => ((chunk: string) => Promise<void>)[],
    ) => {
        await stream(generateRequest, getCallbacks, '/chat/generate/parallelization/aggregate');
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

    /**
     * Get user settings.
     */
    const getUserSettings = async (): Promise<Settings> => {
        return apiFetch<Settings>(`/user/settings`, {
            method: 'GET',
            headers: {
                Accept: 'application/json',
            },
        });
    };

    /**
     * Updates user settings.
     */
    const updateUserSettings = async (settings: Settings): Promise<User> => {
        return apiFetch<User>(`/user/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
            body: settings,
        });
    };

    const uploadFile = async (file: globalThis.File): Promise<string> => {
        if (!file) {
            throw new Error('File cannot be empty for uploadFile');
        }
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiFetch<{ id: string }>(`/user/upload-file`, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
            },
            body: formData,
        });
        return response.id;
    };

    /**
     * Exports a graph by its ID.
     * Downloads the graph as a JSON file.
     */
    const exportGraph = async (graphId: string): Promise<void> => {
        if (!graphId) {
            throw new Error('graphId cannot be empty for exportGraph');
        }
        const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;
        const response = await fetch(`${API_BASE_URL}/graph/${graphId}/backup`, {
            method: 'GET',
            headers: {
                Accept: 'application/json',
                Authorization: `Bearer ${localStorage.getItem('access_token')}`,
            },
            redirect: 'follow',
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(
                `API Error: ${response.status} ${response.statusText}. ${errorText || ''}`,
            );
        }
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `graph-${graphId}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    };

    /**
     * Imports a graph from a JSON file.
     * Expects the file data to be a JSON string representing the graph.
     */
    const importGraph = async (fileData: string): Promise<Graph> => {
        if (!fileData) {
            throw new Error('File data cannot be empty for importGraph');
        }

        return apiFetch<Graph>(`/graph/backup`, {
            method: 'POST',
            headers: {
                Accept: 'application/json',
            },
            body: fileData,
        });
    };

    return {
        getGraphs,
        getGraphById,
        createGraph,
        updateGraph,
        deleteGraph,
        updateGraphName,
        updateGraphConfig,
        getGenerateStream,
        getGenerateParallelizationAggregatorStream,
        getChat,
        getOpenRouterModels,
        getUserSettings,
        updateUserSettings,
        uploadFile,
        exportGraph,
        importGraph,
    };
};
