import type {
    Graph,
    CompleteGraph,
    CompleteGraphRequest,
    Message,
    EdgeRequest,
    NodeRequest,
} from '@/types/graph';
import type { GenerateRequest, ExecutionPlanResponse } from '@/types/chat';
import type { Settings } from '@/types/settings';
import type { ResponseModel } from '@/types/model';
import type { User } from '@/types/user';
import type { FileTreeNode, ContentRequest, GithubCommitState } from '@/types/github';
import type { ExecutionPlanDirectionEnum, NodeTypeEnum } from '@/types/enums';

const { mapEdgeRequestToEdge, mapNodeRequestToNode } = graphMappers();

let isRefreshing = false;
let failedQueue: (() => void)[] = [];

const processQueue = (error: unknown | null) => {
    console.error('Processing failed queue:', error);
    failedQueue.forEach((prom) => prom());
    failedQueue = [];
};

export const useAPI = () => {
    /**
     * Creates a configured fetch request using Nuxt's useFetch
     * @param url The API endpoint URL
     * @param options Fetch options
     * @returns Promise with the response data
     */
    const apiFetch = async <T>(
        url: string,
        options: RequestInit = {},
        bypass401: boolean = false,
    ): Promise<T> => {
        try {
            const data = await $fetch(url, {
                ...options,
                method: options.method as
                    | 'GET'
                    | 'HEAD'
                    | 'PATCH'
                    | 'POST'
                    | 'PUT'
                    | 'DELETE'
                    | 'CONNECT'
                    | 'OPTIONS'
                    | 'TRACE'
                    | undefined,
            });
            return data as T;
        } catch (error: unknown) {
            const err = error as { response?: { status?: number }; data?: { detail?: string } };
            const originalRequest = () => apiFetch<T>(url, options);

            // If the error is not 401, throw it immediately.
            if (err?.response?.status !== 401) {
                const { error } = useToast();
                console.error(`Error fetching ${url}:`, err);
                error(`Failed to fetch ${url}`, { title: 'API Error' });
                throw err;
            }

            // Handle the 401 error (expired access token)
            if (!bypass401 && !isRefreshing) {
                isRefreshing = true;
                try {
                    // Attempt to get a new access token
                    await $fetch('/api/auth/refresh', { method: 'POST' });
                    processQueue(null);
                    // Retry the original request with the new token
                    return await originalRequest();
                } catch (refreshError: unknown) {
                    processQueue(refreshError);
                    // If refresh fails, redirect to login
                    window.location.href = '/auth/login?error=session_expired';
                    return Promise.reject(refreshError);
                } finally {
                    isRefreshing = false;
                }
            }

            if (bypass401) throw err;

            // If a refresh is already in progress, queue the original request
            return new Promise<T>((resolve) => {
                failedQueue.push(() => resolve(originalRequest()));
            });
        }
    };

    /**
     * Fetches all available graphs from the API.
     */
    const getGraphs = async (): Promise<Graph[]> => {
        return apiFetch<Graph[]>(`/api/graphs`, {
            method: 'GET',
        });
    };

    /**
     * Fetches a complete graph by its ID from the API.
     */
    const getGraphById = async (graphId: string): Promise<CompleteGraph> => {
        if (!graphId) throw new Error('graphId is required');
        const data = await apiFetch<CompleteGraphRequest>(`/api/graph/${graphId}`, {
            method: 'GET',
        });
        return {
            graph: data.graph,
            nodes: data.nodes.map(mapNodeRequestToNode),
            edges: data.edges.map(mapEdgeRequestToEdge),
        };
    };

    /**
     * Creates a new graph.
     */
    const createGraph = async (temporary: boolean): Promise<Graph> => {
        return apiFetch<Graph>(`/api/graph/create?temporary=${temporary}`, { method: 'POST' });
    };

    /**
     * Updates an existing graph with the provided data
     */
    const updateGraph = async (
        graphId: string,
        saveData: { graph: Graph; nodes: NodeRequest[]; edges: EdgeRequest[] },
    ): Promise<Graph> => {
        if (!graphId) throw new Error('graphId is required');
        return apiFetch<Graph>(`/api/graph/${graphId}/update`, {
            method: 'POST',
            body: JSON.stringify(saveData),
        });
    };

    /**
     * Updates the name of a graph with the given ID
     */
    const updateGraphName = async (graphId: string, graphName: string): Promise<Graph> => {
        if (!graphId) throw new Error('graphId is required');
        return apiFetch<Graph>(
            `/api/graph/${graphId}/update-name?new_name=${encodeURIComponent(graphName)}`,
            {
                method: 'POST',
            },
        );
    };

    /**
     * Toggles the pinned status of a graph with the given ID
     */
    const togglePin = async (graphId: string, pin: boolean): Promise<Graph> => {
        if (!graphId) throw new Error('graphId is required');
        return apiFetch<Graph>(`/api/graph/${graphId}/pin/${pin}`, {
            method: 'POST',
        });
    };

    /**
     * Persists a temporary graph, making it permanent.
     */
    const persistGraph = async (graphId: string): Promise<Graph> => {
        if (!graphId) throw new Error('graphId is required');
        return apiFetch<Graph>(`/api/graph/${graphId}/persist`, {
            method: 'POST',
        });
    };

    /**
     * Updates the configuration of a graph with the given ID
     */
    const updateGraphConfig = async (
        graphId: string,
        config: Record<string, unknown>,
    ): Promise<Graph> => {
        if (!graphId) throw new Error('graphId is required');
        return apiFetch<Graph>(`/api/graph/${graphId}/update-config`, {
            method: 'POST',
            body: JSON.stringify({ config }),
        });
    };

    /**
     * Deletes a graph by its ID.
     */
    const deleteGraph = async (graphId: string): Promise<void> => {
        if (!graphId) throw new Error('graphId is required');
        await apiFetch<unknown>(`/api/graph/${graphId}`, { method: 'DELETE' });
    };

    /**
     * Fetches chat messages for a specific node in a graph.
     */
    const getChat = async (graphId: string, nodeId: string): Promise<Message[]> => {
        if (!graphId || !nodeId) throw new Error('graphId and nodeId are required');
        return apiFetch<Message[]>(`/api/chat/${graphId}/${nodeId}`, { method: 'GET' });
    };

    const stream = async (
        generateRequest: GenerateRequest,
        getCallbacks: () => ((chunk: string) => Promise<void>)[],
        apiEndpoint: string, // Expects a full path like /api/chat/generate
    ) => {
        const performRequest = async () => {
            const response = await fetch(apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'text/plain' },
                body: JSON.stringify(generateRequest),
            });

            // If the token is expired, throw a specific error to trigger the refresh logic.
            if (response.status === 401) {
                const error = new Error('Unauthorized');
                (error as { response?: { status?: number } }).response = { status: 401 };
                throw error;
            }

            if (!response.ok || !response.body) {
                const errorText = await response.text();
                throw new Error(
                    `API Error: ${response.status} ${response.statusText}. ${errorText}`,
                );
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                await Promise.all(getCallbacks().map((callback) => callback(chunk)));
            }
        };

        try {
            await Promise.all(getCallbacks().map((callback) => callback('[START]')));
            await performRequest();
            await Promise.all(getCallbacks().map(async (callback) => await callback('[END]')));
        } catch (err: unknown) {
            // If the error is not a 401 Unauthorized, handle it as a standard stream failure.
            if ((err as { response?: { status?: number } })?.response?.status !== 401) {
                const { error } = useToast();
                console.error('Failed to fetch stream:', err);
                error(`Failed to fetch stream: ${err}`, { title: 'Stream Error' });
                await Promise.all(getCallbacks().map(async (callback) => await callback('[END]')));
                return;
            }

            // 401 Error Handling: Token Refresh and Retry Logic
            const originalRequest = async () => {
                await performRequest();
                await Promise.all(getCallbacks().map((callback) => callback('[END]')));
            };

            if (!isRefreshing) {
                isRefreshing = true;
                try {
                    await $fetch('/api/auth/refresh', { method: 'POST' });
                    processQueue(null);
                    // Retry the original stream request after successful token refresh.
                    await originalRequest();
                } catch (refreshError: unknown) {
                    processQueue(refreshError);
                    window.location.href = '/auth/login?error=session_expired';
                } finally {
                    isRefreshing = false;
                }
            } else {
                // If a refresh is already in progress, queue this request to be run later.
                return new Promise<void>((resolve) => {
                    failedQueue.push(() => {
                        originalRequest().then(resolve);
                    });
                });
            }
        }
    };

    /**
     * Cancels an ongoing stream for a specific graph and node.
     */
    const cancelStream = async (graphId: string, nodeId: string): Promise<boolean> => {
        if (!graphId || !nodeId) throw new Error('graphId and nodeId are required');
        const res = await apiFetch<{ cancelled: boolean }>(
            `/api/chat/${graphId}/${nodeId}/cancel`,
            { method: 'POST' },
        );
        return res.cancelled;
    };

    /**
     * Fetches a stream of generated text from the API.
     * Note: useFetch doesn't support streaming, so we keep the original fetch implementation
     */
    const getGenerateStream = (
        req: GenerateRequest,
        cb: () => ((chunk: string) => Promise<void>)[],
    ) => stream(req, cb, '/api/chat/generate');

    /**
     * Fetches a stream of generated text from the API for the aggregator of parallelization bloc.
     * Note: useFetch doesn't support streaming, so we keep the original fetch implementation
     */
    const getGenerateParallelizationAggregatorStream = (
        req: GenerateRequest,
        cb: () => ((chunk: string) => Promise<void>)[],
    ) => stream(req, cb, '/api/chat/generate/parallelization/aggregate');

    /**
     * Fetches a stream of generated text from the API for the routing bloc.
     * Note: useFetch doesn't support streaming, so we keep the original fetch implementation
     */
    const getGenerateRoutingStream = (
        req: GenerateRequest,
        cb: () => ((chunk: string) => Promise<void>)[],
    ) => stream(req, cb, '/api/chat/generate/routing');

    /**
     * Fetches the execution plan for a specific node in a graph.
     */
    const getExecutionPlan = async (
        graphId: string,
        nodeId: string,
        direction: ExecutionPlanDirectionEnum,
    ): Promise<ExecutionPlanResponse> => {
        if (!graphId || !nodeId) throw new Error('graphId and nodeId are required');
        return apiFetch<ExecutionPlanResponse>(
            `/api/chat/${graphId}/${nodeId}/execution-plan/${direction}`,
            { method: 'GET' },
        );
    };

    const searchNode = async (
        graphId: string,
        sourceNodeId: string,
        direction: 'upstream' | 'downstream',
        nodeType: NodeTypeEnum[],
    ): Promise<string[]> => {
        return apiFetch<string[]>(`/api/graph/${graphId}/search-node`, {
            method: 'POST',
            body: JSON.stringify({ source_node_id: sourceNodeId, direction, node_type: nodeType }),
        });
    };

    /**
     * Fetches available models from the OpenRouter API.
     */
    const getOpenRouterModels = () => apiFetch<ResponseModel>('/api/models', { method: 'GET' });

    /**
     * Refreshes the list of models from the OpenRouter API.
     * @returns The refreshed list of models.
     */
    const refreshOpenRouterModels = () =>
        apiFetch<ResponseModel>('/api/models/refresh', { method: 'POST' });

    /**
     * Get user settings.
     */
    const getUserSettings = () => apiFetch<Settings>('/api/user/settings', { method: 'GET' });

    /**
     * Updates user settings.
     */
    const updateUserSettings = (settings: Settings) =>
        apiFetch<User>('/api/user/settings', { method: 'POST', body: JSON.stringify(settings) });

    /**
     * Updates the current user's username.
     */
    const updateUsername = (newName: string): Promise<User> => {
        return apiFetch<User>('/api/user/update-name', {
            method: 'POST',
            body: JSON.stringify({ newName }),
        });
    };

    /**
     * Uploads a new user avatar.
     */
    const uploadAvatar = (formData: FormData): Promise<{ avatarUrl: string }> => {
        return apiFetch<{ avatarUrl: string }>('/api/user/avatar', {
            method: 'POST',
            body: formData,
        });
    };

    /**
     * Uploads a file to the server.
     */
    const uploadFile = async (
        file: globalThis.File,
        parentId: string,
    ): Promise<FileSystemObject> => {
        if (!file) throw new Error('File is required');
        const formData = new FormData();
        formData.append('file', file);

        const url = `/api/files/upload?parent_id=${parentId}`;

        return apiFetch<FileSystemObject>(url, {
            method: 'POST',
            body: formData,
        });
    };

    /**
     * Fetches the root folder of the user's file system.
     */
    const getRootFolder = async (): Promise<FileSystemObject> => {
        return apiFetch<FileSystemObject>('/api/files/root', { method: 'GET' });
    };

    /**
     * Fetches the contents of a folder.
     */
    const getFolderContents = async (folderId: string): Promise<FileSystemObject[]> => {
        return apiFetch<FileSystemObject[]>(`/api/files/list/${folderId}`, { method: 'GET' });
    };

    /**
     * Creates a new folder.
     */
    const createFolder = async (
        name: string,
        parentId: string | null,
    ): Promise<FileSystemObject> => {
        return apiFetch<FileSystemObject>('/api/files/folder', {
            method: 'POST',
            body: JSON.stringify({ name, parent_id: parentId }),
        });
    };

    /**
     * Deletes a file or folder.
     */
    const deleteFileSystemObject = async (itemId: string): Promise<void> => {
        await apiFetch<unknown>(`/api/files/${itemId}`, {
            method: 'DELETE',
        });
    };

    /**
     * Fetches a file blob.
     */
    const getFileBlob = async (fileId: string): Promise<Blob> => {
        if (!fileId) throw new Error('fileId is required');

        const performRequest = async (): Promise<Blob> => {
            const response = await fetch(`/api/files/view/${fileId}`, {
                method: 'GET',
            });

            if (response.status === 401) {
                const error = new Error('Unauthorized');
                (error as { response?: { status?: number } }).response = { status: 401 };
                throw error;
            }

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(
                    `API Error: ${response.status} ${response.statusText}. ${errorText}`,
                );
            }
            return response.blob();
        };

        try {
            return await performRequest();
        } catch (err: unknown) {
            if ((err as { response?: { status?: number } })?.response?.status !== 401) {
                const { error } = useToast();
                console.error('Failed to fetch file blob:', err);
                error(`Failed to fetch file: ${err}`, { title: 'File Error' });
                throw err;
            }

            const originalRequest = async () => performRequest();

            if (!isRefreshing) {
                isRefreshing = true;
                try {
                    await $fetch('/api/auth/refresh', { method: 'POST' });
                    processQueue(null);
                    return await originalRequest();
                } catch (refreshError: unknown) {
                    processQueue(refreshError);
                    window.location.href = '/auth/login?error=session_expired';
                    throw refreshError;
                } finally {
                    isRefreshing = false;
                }
            } else {
                return new Promise<Blob>((resolve, reject) => {
                    failedQueue.push(() => {
                        originalRequest().then(resolve).catch(reject);
                    });
                });
            }
        }
    };

    /**
     * Exports a graph by its ID.
     * Downloads the graph as a JSON file.
     */
    const exportGraph = async (graphId: string): Promise<void> => {
        if (!graphId) throw new Error('graphId is required');
        // Use native fetch to handle blob response for file download
        const response = await fetch(`/api/graph/${graphId}/backup`, { method: 'GET' });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error: ${response.status} ${response.statusText}. ${errorText}`);
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
        if (!fileData) throw new Error('File data is required');
        return apiFetch<Graph>(`/api/graph/backup`, { method: 'POST', body: fileData });
    };

    /**
     * Fetches the file tree of a GitHub repository.
     */
    const getRepoTree = async (
        owner: string,
        repo: string,
        branch: string,
        force_pull: boolean,
    ): Promise<FileTreeNode | null> => {
        if (!repo || !owner || !branch) return null;

        const url = `/api/github/repos/${owner}/${repo}/tree?branch=${encodeURIComponent(branch)}&force_pull=${force_pull}`;
        return apiFetch<FileTreeNode>(url, {
            method: 'GET',
        });
    };

    /**
     * Fetches a specific file from a GitHub repository.
     */
    const getRepoFile = async (
        owner: string,
        repo: string,
        path: string,
        branch: string,
    ): Promise<ContentRequest | null> => {
        if (!repo || !owner || !path || !branch) return null;

        const url = `/api/github/repos/${owner}/${repo}/contents/${path}?branch=${encodeURIComponent(
            branch,
        )}`;
        return apiFetch<ContentRequest>(url);
    };

    /**
     * Fetches the branches of a GitHub repository.
     */
    const getRepoBranches = async (owner: string, repo: string): Promise<string[] | null> => {
        if (!repo || !owner) return null;

        return apiFetch<string[]>(`/api/github/repos/${owner}/${repo}/branches`);
    };

    /**
     * Fetches the commit state of a specific branch in a GitHub repository.
     */
    const getRepoCommitState = async (
        owner: string,
        repo: string,
        branch: string,
    ): Promise<GithubCommitState | null> => {
        if (!repo || !owner || !branch) return null;

        const url = `/api/github/repos/${owner}/${repo}/commit/state?branch=${encodeURIComponent(
            branch,
        )}`;
        return apiFetch<GithubCommitState>(url);
    };

    return {
        apiFetch,
        getGraphs,
        getGraphById,
        createGraph,
        updateGraph,
        deleteGraph,
        updateGraphName,
        togglePin,
        persistGraph,
        updateGraphConfig,
        getGenerateStream,
        getExecutionPlan,
        searchNode,
        cancelStream,
        getGenerateParallelizationAggregatorStream,
        getGenerateRoutingStream,
        getChat,
        getOpenRouterModels,
        refreshOpenRouterModels,
        getUserSettings,
        updateUserSettings,
        updateUsername,
        uploadAvatar,
        uploadFile,
        getRootFolder,
        getFolderContents,
        createFolder,
        deleteFileSystemObject,
        getFileBlob,
        exportGraph,
        importGraph,
        getRepoTree,
        getRepoFile,
        getRepoBranches,
        getRepoCommitState,
    };
};
