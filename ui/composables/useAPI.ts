import type { Graph, CompleteGraph, CompleteGraphRequest } from "@/types/graph";
const {
    mapEdgeRequestToEdge,
    mapNodeRequestToNode,
    mapNodeToNodeRequest,
    mapEdgeToEdgeRequest,
} = graphMappers();

interface ApiError {
    detail?: string | object;
}

const API_BASE_URL = "http://localhost:8000";

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
            let errorData:
                | ApiError
                | string = `HTTP error ${response.status}: ${response.statusText}`;
            try {
                const body = await response.json();
                errorData = body || errorData;
            } catch (e) {}
            console.error("API Request Failed:", errorData);
            throw new Error(
                typeof errorData === "string"
                    ? errorData
                    : JSON.stringify(errorData)
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
                method: "GET",
                headers: {
                    Accept: "application/json",
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
        try {
            const response = await fetch(`${API_BASE_URL}/graph/${graphId}`, {
                method: "GET",
                headers: {
                    Accept: "application/json",
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
                method: "POST",
                headers: {
                    Accept: "application/json",
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
        saveData: CompleteGraph
    ): Promise<Graph> => {
        if (!graphId) {
            throw new Error("graphId cannot be empty for updateGraph");
        }
        try {
            const response = await fetch(
                `${API_BASE_URL}/graph/${graphId}/update`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                    },
                    body: JSON.stringify({
                        graph: saveData.graph,
                        nodes: saveData.nodes.map((node) =>
                            mapNodeToNodeRequest(node, graphId)
                        ),
                        edges: saveData.edges.map((edge) =>
                            mapEdgeToEdgeRequest(edge, graphId)
                        ),
                    }),
                }
            );
            const data = await handleResponse<Graph>(response);
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
    };
};
