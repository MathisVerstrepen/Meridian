import copy
import logging
import uuid
from typing import Any, Optional

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

NODE_UPDATABLE_FIELDS = (
    "type",
    "position_x",
    "position_y",
    "width",
    "height",
    "parent_node_id",
    "data",
)

EDGE_UPDATABLE_FIELDS = (
    "source_node_id",
    "target_node_id",
    "source_handle_id",
    "target_handle_id",
    "type",
    "label",
    "animated",
    "style",
    "data",
    "markerEnd",
)


def _normalize_node_dimension(value: Any) -> str:
    if value is None:
        return "100px"

    if isinstance(value, (int, float)):
        normalized_value = int(value) if isinstance(value, float) and value.is_integer() else value
        return f"{normalized_value}px"

    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            return "100px"

        try:
            numeric_value = float(stripped_value)
        except ValueError:
            return stripped_value

        normalized_value = int(numeric_value) if numeric_value.is_integer() else numeric_value
        return f"{normalized_value}px"

    return str(value)


def _sync_model_fields(target: Any, source: Any, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        new_value = getattr(source, field_name)
        if getattr(target, field_name) != new_value:
            setattr(target, field_name, new_value)


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
    Atomically updates a graph's properties and syncs its nodes and edges.

    Args:
        engine (AsyncEngine): The SQLAlchemy async engine instance.
        graph_id (str): The UUID of the graph to update.
        graph_update_data (Graph): An object containing the fields to update on the Graph
                                   (e.g., name, description). Should NOT contain nodes/edges.
        nodes (list[Node]): The desired final set of nodes for the graph.
        edges (list[Edge]): The desired final set of edges for the graph.

    Returns:
        Graph: The updated Graph ORM object, reflecting the changes.

    Raises:
        HTTPException: Status 404 if the graph with the given graph_id is not found.
        SQLAlchemyError: If any database operation fails during the transaction.
    """
    graph_uuid = uuid.UUID(graph_id)

    for node in nodes:
        node.graph_id = graph_uuid
        node.width = _normalize_node_dimension(node.width)
        node.height = _normalize_node_dimension(node.height)

    for edge in edges:
        edge.graph_id = graph_uuid

    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            # Scope updates to the owning user. If the graph exists for another user,
            # treat it as missing rather than creating a conflicting replacement.
            stmt = (
                select(Graph)
                .where(and_(Graph.id == graph_id, Graph.user_id == user_id))
                .with_for_update()
            )
            result = await session.exec(stmt)  # type: ignore
            db_graph: Graph = result.scalar_one_or_none()

            if db_graph:
                db_graph.updated_at = func.now()  # type: ignore

            else:
                existing_graph_stmt = select(Graph).where(and_(Graph.id == graph_id))
                existing_graph_result = await session.exec(existing_graph_stmt)  # type: ignore
                existing_graph = existing_graph_result.scalar_one_or_none()
                if existing_graph:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Graph with id {graph_id} not found",
                    )

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

            with session.no_autoflush:
                existing_nodes_stmt = (
                    select(Node).where(and_(Node.graph_id == graph_uuid)).with_for_update()
                )
                existing_edges_stmt = (
                    select(Edge).where(and_(Edge.graph_id == graph_uuid)).with_for_update()
                )

                existing_nodes_result = await session.exec(existing_nodes_stmt)  # type: ignore
                existing_edges_result = await session.exec(existing_edges_stmt)  # type: ignore

                existing_nodes_by_id = {
                    existing_node.id: existing_node
                    for existing_node in existing_nodes_result.scalars().all()
                }
                existing_edges_by_id = {
                    existing_edge.id: existing_edge
                    for existing_edge in existing_edges_result.scalars().all()
                }

                incoming_node_ids = {node.id for node in nodes}
                incoming_edge_ids = {edge.id for edge in edges}

                edge_ids_to_delete = [
                    edge_id for edge_id in existing_edges_by_id if edge_id not in incoming_edge_ids
                ]
                if edge_ids_to_delete:
                    await session.exec(
                        delete(Edge).where(
                            and_(
                                Edge.graph_id == graph_uuid,
                                Edge.id.in_(edge_ids_to_delete),  # type: ignore[attr-defined]
                            )
                        )
                    )  # type: ignore

                for node in nodes:
                    if existing_node := existing_nodes_by_id.pop(node.id, None):
                        _sync_model_fields(existing_node, node, NODE_UPDATABLE_FIELDS)
                    else:
                        session.add(node)

                for edge in edges:
                    if existing_edge := existing_edges_by_id.pop(edge.id, None):
                        _sync_model_fields(existing_edge, edge, EDGE_UPDATABLE_FIELDS)
                    else:
                        session.add(edge)

                node_ids_to_delete = [
                    node_id for node_id in existing_nodes_by_id if node_id not in incoming_node_ids
                ]
                if node_ids_to_delete:
                    await session.exec(
                        delete(Node).where(
                            and_(
                                Node.graph_id == graph_uuid,
                                Node.id.in_(node_ids_to_delete),  # type: ignore[attr-defined]
                            )
                        )
                    )  # type: ignore

            await session.flush()

            # --- Neo4j Update ---
            try:
                graph_id_str = str(graph_id)
                await update_neo4j_graph(neo4j_driver, graph_id_str, nodes, edges)
            except (Neo4jError, Exception) as e:
                logger.error(f"Neo4j operation failed, triggering PostgreSQL rollback: {e}")
                raise e

        await session.refresh(db_graph, attribute_names=["nodes", "edges"])

        db_graph.node_count = len(db_graph.nodes)

        return db_graph


async def get_nodes_by_ids(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: str, node_ids: list[str]
) -> list[Node]:
    """
    Retrieve nodes by their IDs from the database.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the
            database.
        graph_id (uuid.UUID): The UUID of the graph to which the nodes belong.
        node_ids (list[uuid.UUID]): A list of UUIDs representing the IDs of the nodes to retrieve.

    Returns:
        list[Node]: A list of Node objects matching the provided IDs.
    """

    if not node_ids:
        return []

    async with AsyncSession(pg_engine) as session:
        stmt = select(Node).where(
            and_(Node.graph_id == graph_id, Node.id.in_(node_ids))  # type: ignore
        )
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


async def update_node_data(
    pg_engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    node_id: str,
    data: dict,
) -> None:
    """
    Update the data field of a node in the database.
    Uses pessimistic locking to handle concurrent updates safely.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            try:
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

                db_node.data = {**(db_node.data or {}), **data}
                attributes.flag_modified(db_node, "data")

                await session.flush()

            except Exception as e:
                logger.error(f"Error updating node data for node {node_id}: {e}")
                raise
