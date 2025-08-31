import copy
import logging
import uuid
from typing import Optional

from database.neo4j.crud import update_neo4j_graph
from database.pg.models import Edge, Graph, Node
from fastapi import HTTPException
from models.message import NodeTypeEnum
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlalchemy.orm import attributes
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def update_graph_with_nodes_and_edges(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    user_id: str,
    graph_update_data: Graph,
    nodes: list[Node],
    edges: list[Edge],
) -> Graph:
    """
    Atomically updates a graph's properties and replaces its nodes and edges.

    Args:
        engine (AsyncEngine): The SQLAlchemy async engine instance.
        graph_id (str): The UUID of the graph to update.
        graph_update_data (Graph): An object containing the fields to update on the Graph
                                   (e.g., name, description). Should NOT contain nodes/edges.
        nodes (list[Node]): A list of the NEW Node ORM objects to be associated with the graph.
                            These should NOT be associated with a session yet.
        edges (list[Edge]): A list of the NEW Edge ORM objects to be associated with the graph.
                            These should NOT be associated with a session yet.

    Returns:
        Graph: The updated Graph ORM object, reflecting the changes.

    Raises:
        HTTPException: Status 404 if the graph with the given graph_id is not found.
        SQLAlchemyError: If any database operation fails during the transaction.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            # Fetch the graph using a locking select to ensure no other transaction modifies it
            stmt = select(Graph).where(and_(Graph.id == graph_id)).with_for_update()
            result = await session.exec(stmt)  # type: ignore
            db_graph: Graph = result.scalar_one_or_none()

            if db_graph:
                db_graph.updated_at = func.now()  # type: ignore

            else:
                db_graph = Graph(
                    id=graph_id,
                    user_id=user_id,
                    name=graph_update_data.name,
                    description=graph_update_data.description,
                    custom_instructions=graph_update_data.custom_instructions,
                    max_tokens=graph_update_data.max_tokens,
                    temperature=graph_update_data.temperature,
                    top_p=graph_update_data.top_p,
                    top_k=graph_update_data.top_k,
                    frequency_penalty=graph_update_data.frequency_penalty,
                    presence_penalty=graph_update_data.presence_penalty,
                    repetition_penalty=graph_update_data.repetition_penalty,
                    reasoning_effort=graph_update_data.reasoning_effort,
                )
                session.add(db_graph)

            # Fetch the current data field of all nodes in the graph
            stmt_old_nodes = select(Node.id, Node.data, Node.type).where(Node.graph_id == graph_id)  # type: ignore
            old_nodes_result = await session.exec(stmt_old_nodes)

            # Create a lookup dictionary: {node_id: usageData_dict}
            preserved_node_data = {
                node_id: {"data": data, "type": node_type}
                for node_id, data, node_type in old_nodes_result.all()
                if data
            }

            # Clear existing nodes and edges in the graph
            with session.no_autoflush:
                await session.exec(delete(Edge).where(and_(Edge.graph_id == graph_id)))  # type: ignore
                await session.exec(delete(Node).where(and_(Node.graph_id == graph_id)))  # type: ignore

            # Ensure deletes are executed before adds
            await session.flush()

            # Re-add nodes and edges with the new graph_id
            if nodes:
                for node in nodes:
                    node.graph_id = uuid.UUID(graph_id)
                    old_node_info = preserved_node_data.get(node.id)

                    if old_node_info:
                        old_data = old_node_info["data"]

                        # --- SPECIAL HANDLING FOR PARALLELIZATION NODES ---
                        if old_node_info["type"] == NodeTypeEnum.PARALLELIZATION:
                            old_models = old_data.get("models", [])
                            new_models = node.data["models"] if isinstance(node.data, dict) else []

                            if isinstance(old_models, list) and isinstance(new_models, list):
                                # Create a map of old usage data for quick lookup
                                old_models_usage_map = {
                                    model.get("id"): model.get("usageData")
                                    for model in old_models
                                    if isinstance(model, dict) and model.get("usageData")
                                }

                                # Merge usageData into the new models from the frontend
                                for new_model in new_models:
                                    if isinstance(new_model, dict):
                                        model_id = new_model.get("id")
                                        if usage_data := old_models_usage_map.get(model_id):
                                            new_model["usageData"] = usage_data

                                # Merge aggregator usageData
                                if isinstance(old_data["aggregator"], dict):
                                    if isinstance(old_data.get("aggregator"), dict):
                                        if not isinstance(node.data, dict):
                                            node.data = {}
                                        node.data.setdefault("aggregator", {})["usageData"] = (
                                            old_data["aggregator"].get("usageData")
                                        )

                        # --- Standard handling for other node types ---
                        else:
                            if usage_data_to_restore := old_data.get("usageData"):
                                if node.data is None:
                                    node.data = {}
                                if not isinstance(node.data, dict):
                                    node.data = {}
                                node.data["usageData"] = usage_data_to_restore

                session.add_all(nodes)

            if edges:
                for edge in edges:
                    edge.graph_id = uuid.UUID(graph_id)
                session.add_all(edges)

            # --- Neo4j Update ---
            try:
                graph_id_str = str(graph_id)
                await update_neo4j_graph(neo4j_driver, graph_id_str, nodes, edges)
            except (Neo4jError, Exception) as e:
                logger.error(f"Neo4j operation failed, triggering PostgreSQL rollback: {e}")
                raise e

        await session.refresh(db_graph, attribute_names=["nodes", "edges"])
        return db_graph


async def get_nodes_by_ids(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: str, node_ids: list[str]
) -> list[Node]:
    """
    Retrieve nodes by their IDs from the database.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the database.
        graph_id (uuid.UUID): The UUID of the graph to which the nodes belong.
        node_ids (list[uuid.UUID]): A list of UUIDs representing the IDs of the nodes to retrieve.

    Returns:
        list[Node]: A list of Node objects matching the provided IDs.
    """

    if not node_ids:
        return []

    async with AsyncSession(pg_engine) as session:
        stmt = select(Node).where(and_(Node.graph_id == graph_id, Node.id.in_(node_ids)))  # type: ignore
        result = await session.exec(stmt)  # type: ignore
        nodes_found = result.scalars().all()

        nodes_map = {str(node.id): node for node in nodes_found}

        ordered_nodes = [nodes_map[node_id] for node_id in node_ids if node_id in nodes_map]

        return ordered_nodes


async def update_node_usage_data(
    pg_engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    node_id: str,
    usage_data: dict,
    node_type: NodeTypeEnum,
    model_id: Optional[str] = None,
) -> None:
    """
    Update the usage data of a node in the database.
    Uses pessimistic locking to handle concurrent updates safely.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            try:
                # Use pessimistic locking to prevent read-modify-write race conditions
                stmt = (
                    select(Node)
                    .where(and_(Node.graph_id == graph_id, Node.id == node_id))
                    .with_for_update()
                )
                result = await session.exec(stmt)  # type: ignore
                db_node = result.scalar_one_or_none()

                if not db_node:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Node with id {node_id} and graph_id {graph_id} not found",
                    )

                if db_node.data is None:
                    db_node.data = {}

                data = copy.deepcopy(db_node.data) if db_node.data else {}

                if node_type == NodeTypeEnum.PARALLELIZATION:
                    if model_id:
                        # update for a specific model within the parallelization node
                        if "models" in data and isinstance(data["models"], list):
                            model_found = False
                            for model in data["models"]:
                                if model.get("id") == model_id:
                                    model["usageData"] = usage_data
                                    model_found = True
                                    break

                            if not model_found:
                                logger.warning(
                                    f"Model with id {model_id} not found in node {node_id}"
                                )
                        else:
                            logger.warning(
                                f"No 'models' list found in parallelization node {node_id}"
                            )
                    else:
                        # update for the aggregator of the parallelization node
                        if "aggregator" not in data:
                            data["aggregator"] = {}
                        data["aggregator"]["usageData"] = usage_data
                else:
                    data["usageData"] = usage_data

                db_node.data = data
                attributes.flag_modified(db_node, "data")

                await session.flush()

            except Exception as e:
                logger.error(f"Error updating node usage data for node {node_id}: {e}")
                raise
