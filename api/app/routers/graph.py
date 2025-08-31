import uuid

from database.pg.graph_ops.graph_config_crud import (
    GraphConfigUpdate,
    update_graph_config,
    update_graph_name,
)
from database.pg.graph_ops.graph_crud import (
    CompleteGraph,
    create_empty_graph,
    delete_graph,
    get_all_graphs,
    get_graph_by_id,
)
from database.pg.graph_ops.graph_node_crud import update_graph_with_nodes_and_edges
from database.pg.models import Graph
from fastapi import APIRouter, Depends, Request
from models.graphDTO import NodeSearchRequest
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.graph_service import search_graph_nodes

router = APIRouter()


@router.get("/graphs")
async def route_get_graphs(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> list[Graph]:
    """
    Retrieve all graphs.

    This endpoint retrieves all graphs from the database.

    Returns:
        List[Graph]: A list of Graph objects.
    """

    return await get_all_graphs(request.app.state.pg_engine, user_id)


@router.get("/graph/{graph_id}")
async def route_get_graph_by_id(
    request: Request,
    graph_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CompleteGraph:
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
async def route_create_new_empty_graph(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> Graph:
    """
    Create a new graph.

    This endpoint creates a new graph empty in the database.

    Returns:
        Graph: The created Graph object.
    """

    graph = await create_empty_graph(request.app.state.pg_engine, user_id)
    return graph


@router.post("/graph/{graph_id}/update")
async def route_update_graph(
    request: Request,
    graph_id: str,
    graph_save_request: CompleteGraph,
    user_id: str = Depends(get_current_user_id),
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
        user_id,
        graph_save_request.graph,
        graph_save_request.nodes,
        graph_save_request.edges,
    )
    return graph


@router.post("/graph/{graph_id}/update-name")
async def route_rename_graph(
    request: Request,
    graph_id: str,
    new_name: str,
    user_id: str = Depends(get_current_user_id),
) -> Graph:
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


class ConfigUpdateRequest(BaseModel):
    config: GraphConfigUpdate


@router.post("/graph/{graph_id}/update-config")
async def route_update_graph_config(
    request: Request,
    graph_id: str,
    config: ConfigUpdateRequest,
    user_id: str = Depends(get_current_user_id),
) -> Graph:
    """
    Update the configuration of a graph.

    This endpoint updates the configuration of a graph in the database.

    Args:
        graph_id (int): The ID of the graph to update.
        config (GraphConfigUpdate): The new configuration for the graph.

    Returns:
        Graph: The updated Graph object.
    """
    graph_id = uuid.UUID(graph_id)

    graph = await update_graph_config(request.app.state.pg_engine, graph_id, config.config)
    return graph


@router.delete("/graph/{graph_id}")
async def route_delete_graph(
    request: Request,
    graph_id: str,
    user_id: str = Depends(get_current_user_id),
) -> None:
    """
    Delete a graph.

    This endpoint deletes a graph from the database.

    Args:
        graph_id (int): The ID of the graph to delete.

    Returns:
        None
    """
    graph_id = uuid.UUID(graph_id)

    await delete_graph(request.app.state.pg_engine, request.app.state.neo4j_driver, graph_id)
    return None


@router.post("/graph/{graph_id}/search-node")
async def search_graph_nodes_endpoint(
    request: Request,
    graph_id: str,
    search_request: NodeSearchRequest,
    user_id: str = Depends(get_current_user_id),
) -> list[str]:
    """
    Search for nodes in a graph.

    This endpoint searches for nodes in the specified graph that match the given query.

    Args:
        graph_id (int): The ID of the graph to search.
        query (str): The search query to match against node properties.

    Returns:
        list[Node]: A list of matching Node objects.
    """
    graph_id = uuid.UUID(graph_id)

    node = await search_graph_nodes(request.app.state.neo4j_driver, graph_id, search_request)
    return node


@router.get("/graph/{graph_id}/backup")
async def export_graph_as_json(
    request: Request,
    graph_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> CompleteGraph:
    """
    Retrieves a complete representation of a single graph, including its properties,
    nodes, and edges.

    Args:
        graph_id (uuid.UUID): The ID of the graph to retrieve.

    Returns:
        CompleteGraph: A Pydantic object containing the graph, nodes, and edges schemas.
    """

    return await get_graph_by_id(request.app.state.pg_engine, graph_id)


@router.post("/graph/backup")
async def restore_graph_from_json(
    request: Request,
    backup_data: CompleteGraph,
    user_id: str = Depends(get_current_user_id),
) -> Graph:
    """
    Restores a graph's state from a JSON backup. The new graph is attached to the user
    who initiated the restore operation, not the user who created the backup.

    Args:
        backup_data (CompleteGraph): A JSON object containing the full graph state,
          including the graph's properties, nodes, and edges.

    Returns:
        Graph: The updated Graph object after restoring from the backup.
    """

    graph_id = uuid.UUID(backup_data.graph.id)

    updated_graph = await update_graph_with_nodes_and_edges(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=graph_id,
        user_id=user_id,
        graph_update_data=backup_data.graph,
        nodes=backup_data.nodes,
        edges=backup_data.edges,
    )

    return updated_graph
