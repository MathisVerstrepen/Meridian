from fastapi import APIRouter, Request
import uuid

from database.pg.models import Graph
from database.pg.crud import (
    CompleteGraph,
    create_empty_graph,
    get_all_graphs,
    get_graph_by_id,
    update_graph_with_nodes_and_edges,
    update_graph_name,
    delete_graph,
)

router = APIRouter()


@router.get("/graphs")
async def route_get_graphs(request: Request) -> list[Graph]:
    """
    Retrieve all graphs.

    This endpoint retrieves all graphs from the database.

    Returns:
        List[Graph]: A list of Graph objects.
    """

    graphs = await get_all_graphs(request.app.state.pg_engine)
    return graphs


@router.get("/graph/{graph_id}")
async def route_get_graph_by_id(request: Request, graph_id: str) -> CompleteGraph:
    """
    Retrieve a graph by its ID.

    This endpoint retrieves a graph by its ID, including its nodes and edges.

    Args:
        graph_id (int): The ID of the graph to retrieve.

    Returns:
        CompleteGraph: A Pydantic object containing the graph, nodes, and edges schemas.
    """
    graph_id = uuid.UUID(graph_id)
    complete_graph = await get_graph_by_id(request.app.state.pg_engine, graph_id)
    return complete_graph


@router.post("/graph/create")
async def route_create_new_empty_graph(request: Request) -> Graph:
    """
    Create a new graph.

    This endpoint creates a new graph empty in the database.

    Returns:
        Graph: The created Graph object.
    """

    graph = await create_empty_graph(request.app.state.pg_engine)
    return graph


@router.post("/graph/{graph_id}/update")
async def route_update_graph(
    request: Request, graph_id: str, graph_save_request: CompleteGraph
) -> Graph:
    """
    Save a graph.

    This endpoint saves a graph in the database.

    Args:
        graph_id (int): The ID of the graph to save.
        graph_save_request (GraphSaveRequest): The request body containing the graph data.

    Returns:
        Graph: The saved Graph object.
    """

    graph_id = uuid.UUID(graph_id)

    graph = await update_graph_with_nodes_and_edges(
        request.app.state.pg_engine,
        request.app.state.neo4j_driver,
        graph_id,
        graph_save_request.graph,
        graph_save_request.nodes,
        graph_save_request.edges,
    )
    return graph


@router.post("/graph/{graph_id}/update-name")
async def route_rename_graph(request: Request, graph_id: str, new_name: str) -> Graph:
    """
    Rename a graph.

    This endpoint renames a graph in the database.

    Args:
        graph_id (int): The ID of the graph to rename.
        new_name (str): The new name for the graph.

    Returns:
        Graph: The renamed Graph object.
    """

    graph_id = uuid.UUID(graph_id)

    graph = await update_graph_name(
        request.app.state.pg_engine,
        graph_id,
        new_name,
    )
    return graph


@router.delete("/graph/{graph_id}")
async def route_delete_graph(request: Request, graph_id: str) -> None:
    """
    Delete a graph.

    This endpoint deletes a graph from the database.

    Args:
        graph_id (int): The ID of the graph to delete.

    Returns:
        None
    """
    graph_id = uuid.UUID(graph_id)

    await delete_graph(
        request.app.state.pg_engine, request.app.state.neo4j_driver, graph_id
    )
    return None
