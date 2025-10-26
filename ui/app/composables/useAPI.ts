import type {
    Graph,
    CompleteGraph,
    CompleteGraphRequest,
    Message,
    EdgeRequest,
    NodeRequest,
} from '@/types/graph';
import type { ExecutionPlanResponse } from '@/types/chat';
import type { Settings } from '@/types/settings';
import type { ResponseModel } from '@/types/model';
import type { User, AllUsageResponse } from '@/types/user';
import type {
    FileTreeNode,
    ContentRequest,
    GithubCommitState,
    RepositoryInfo,
} from '@/types/github';
import type { ExecutionPlanDirectionEnum, NodeTypeEnum } from '@/types/enums';

const { mapEdgeRequestToEdge, mapNodeRequestToNode } = graphMappers();

let refreshPromise: Promise<void> | null = null;

/**
 * Handles refreshing the authentication token. It ensures that only one
 * refresh request is active at any given time. Subsequent calls while a
 * refresh is in progress will wait for the current one to complete.
 * @returns A promise that resolves upon successful token refresh and rejects on failure.
 */
const handleTokenRefresh = (): Promise<void> => {
    // If a refresh is already in progress, return the existing promise.
    if (refreshPromise) {
        return refreshPromise;
    }

    // Start a new refresh process.
    refreshPromise = new Promise((resolve, reject) => {
        const performRefresh = async () => {
            try {
                await $fetch('/api/auth/refresh', { method: 'POST' });
                resolve();
            } catch (refreshError) {
                // If refresh fails, redirect to login and reject the promise.
                window.location.href = '/auth/login?error=session_expired';
                reject(refreshError);
            } finally {
                // Reset the promise once the process is complete, allowing for future refreshes.
                refreshPromise = null;
            }
        };
        performRefresh();
    });

    return refreshPromise;
};

export const useAPI = () => {
    /**
     * Creates a configured fetch request using Nuxt's useFetch. It automatically
     * handles token refreshing on 401 errors.
     * @param url The API endpoint URL
     * @param options Fetch options
     * @param bypass401 If true, will not attempt to refresh token on 401.
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

            // If the error is a 401 and not bypassed, attempt a token refresh and retry.
            if (err?.response?.status === 401 && !bypass401) {
                try {
                    await handleTokenRefresh();
                    // Retry the request after a successful refresh.
                    // The new token is automatically included in the cookies.
                    return await $fetch(url, {
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
                } catch (refreshOrRetryError) {
                    // If refresh failed, handleTokenRefresh would have redirected.
                    // If retry failed, throw the new error to be handled by the generic handler.
                    const { error: toastError } = useToast();
                    console.error(
                        `Error fetching ${url} after token refresh:`,
                        refreshOrRetryError,
                    );
                    toastError(`Failed to fetch ${url}`, { title: 'API Error' });
                    throw refreshOrRetryError;
                }
            }

            // For non-401 errors, bypassed 401s, or errors on retry, handle them here.
            const { error: toastError } = useToast();
            console.error(`Error fetching ${url}:`, err);
            toastError(`Failed to fetch ${url}`, { title: 'API Error' });
            throw err;
        }
    };

    /**
     * A wrapper for native `fetch` calls that includes automatic token refresh
     * and retry logic on 401 Unauthorized errors.
     * @param requestFn A function that returns a promise from a fetch call.
     * @param errorTitle The title to display in error toast notifications.
     * @returns The result of the request function.
     */
    const fetchWithRefresh = async <T>(
        requestFn: () => Promise<T>,
        errorTitle: string = 'API Error',
    ): Promise<T> => {
        try {
            return await requestFn();
        } catch (error: unknown) {
            const err = error as { response?: { status?: number } };

            // If it's a 401, attempt refresh and retry.
            if (err?.response?.status === 401) {
                try {
                    await handleTokenRefresh();
                    return await requestFn(); // Retry after successful refresh.
                } catch (refreshOrRetryError) {
                    const { error: toastError } = useToast();
                    console.error('Request failed after token refresh:', refreshOrRetryError);
                    toastError(`Request failed: ${refreshOrRetryError}`, {
                        title: errorTitle,
                    });
                    throw refreshOrRetryError;
                }
            }

            // Handle non-401 errors.
            const { error: toastError } = useToast();
            console.error('Request failed:', error);
            toastError(`Request failed: ${error}`, { title: errorTitle });
            throw error;
        }
    };

    /**
     * Fetches the short-lived auth token for establishing a WebSocket connection.
     */
    const getWebSocketToken = (): Promise<{ token: string }> => {
        return apiFetch<{ token: string }>('/api/auth/ws-token', { method: 'GET' });
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

        return fetchWithRefresh(performRequest, 'File Error');
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

    // --- GitLab ---
    const connectGitLab = (
        personalAccessToken: string,
        privateKey: string,
        instanceUrl: string,
    ) => {
        return apiFetch('/api/auth/gitlab/connect', {
            method: 'POST',
            body: JSON.stringify({
                personal_access_token: personalAccessToken,
                private_key: privateKey,
                instance_url: instanceUrl,
            }),
        });
    };

    const disconnectGitLab = () => {
        return apiFetch('/api/auth/gitlab/disconnect', { method: 'POST' });
    };

    // --- Generic Repositories ---
    const listRepositories = (): Promise<RepositoryInfo[]> => {
        return apiFetch<RepositoryInfo[]>('/api/repositories');
    };

    const cloneRepository = (
        provider: string,
        fullName: string,
        cloneUrl: string,
        cloneMethod: 'ssh' | 'https',
    ) => {
        return apiFetch('/api/repositories/clone', {
            method: 'POST',
            body: JSON.stringify({
                provider,
                full_name: fullName,
                clone_url: cloneUrl,
                clone_method: cloneMethod,
            }),
        });
    };

    const getGenericRepoTree = async (
        provider: string,
        owner: string,
        repo: string,
        branch: string,
    ): Promise<FileTreeNode | null> => {
        if (!provider || !repo || !owner || !branch) return null;
        const url = `/api/repositories/${provider}/${owner}/${repo}/tree?branch=${encodeURIComponent(
            branch,
        )}`;
        return apiFetch<FileTreeNode>(url, { method: 'GET' });
    };

    const getGenericRepoFile = async (
        provider: string,
        owner: string,
        repo: string,
        path: string,
        branch: string,
    ): Promise<ContentRequest | null> => {
        if (!provider || !repo || !owner || !path || !branch) return null;
        const url = `/api/repositories/${provider}/${owner}/${repo}/content/${path}?branch=${encodeURIComponent(
            branch,
        )}`;
        return apiFetch<ContentRequest>(url);
    };

    const getGenericRepoBranches = async (
        provider: string,
        owner: string,
        repo: string,
    ): Promise<string[] | null> => {
        if (!provider || !repo || !owner) return null;
        return apiFetch<string[]>(`/api/repositories/${provider}/${owner}/${repo}/branches`);
    };

    const pullGenericRepo = (provider: string, owner: string, repo: string, branch: string) => {
        const url = `/api/repositories/${provider}/${owner}/${repo}/pull?branch=${encodeURIComponent(
            branch,
        )}`;
        return apiFetch(url, { method: 'POST' });
    };

    /**
     * Fetches the commit state of a specific branch in a GitHub repository.
     * Note: This is GitHub specific and will be deprecated.
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

    /**
     * Fetches user usage data.
     */
    const getUsage = async (): Promise<AllUsageResponse | null> => {
        return apiFetch<AllUsageResponse>('/api/user/usage');
    };

    return {
        apiFetch,
        fetchWithRefresh,
        getWebSocketToken,
        getGraphs,
        getGraphById,
        createGraph,
        updateGraph,
        deleteGraph,
        updateGraphName,
        togglePin,
        persistGraph,
        updateGraphConfig,
        getExecutionPlan,
        searchNode,
        getChat,
        getOpenRouterModels,
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
        connectGitLab,
        disconnectGitLab,
        // --- Generic Repositories ---
        listRepositories,
        cloneRepository,
        getGenericRepoTree,
        getGenericRepoFile,
        getGenericRepoBranches,
        pullGenericRepo,
        // --- Deprecated GitHub specific ---
        getRepoCommitState,
        getUsage,
    };
};
