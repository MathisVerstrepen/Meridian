from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, delete, join
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
import uuid
from pydantic import BaseModel
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError

from database.pg.models import Graph, Node, Edge
from database.neo4j.crud import update_neo4j_graph


class CompleteGraph(BaseModel):
    graph: Graph
    nodes: list[Node]
    edges: list[Edge]


async def get_all_graphs(engine: SQLAlchemyAsyncEngine) -> list[Graph]:
    """
    Retrieve all graphs from the database.

    This function retrieves all graphs from the database using the provided engine.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the database.

    Returns:
        list[Graph]: A list of Graph objects.
    """
    async with AsyncSession(engine) as session:
        stmt = select(Graph).order_by(Graph.updated_at.desc())
        result = await session.exec(stmt)
        graphs = result.scalars().all()
        return graphs


async def get_graph_by_id(
    engine: SQLAlchemyAsyncEngine, graph_id: uuid.UUID
) -> CompleteGraph:
    """
    Retrieve a graph by its ID, including its nodes and edges, from the database.

    Args:
        engine (AsyncEngine): The SQLAlchemy async engine instance connected to the database.
        graph_id (uuid.UUID): The UUID of the graph to retrieve.

    Returns:
        CompleteGraph: A Pydantic object containing the graph, nodes, and edges schemas.

    Raises:
        HTTPException: Status 404 if the graph with the given ID is not found.
        SQLAlchemyError: If any database operation fails.
    """
    async with AsyncSession(engine) as session:
        options = [selectinload(Graph.nodes), selectinload(Graph.edges)]
        db_graph = await session.get(Graph, graph_id, options=options)

        if not db_graph:
            raise HTTPException(
                status_code=404, detail=f"Graph with id {graph_id} not found"
            )

        print(db_graph.nodes)

        complete_graph_response = CompleteGraph(
            graph=db_graph,
            nodes=db_graph.nodes,
            edges=db_graph.edges,
        )

        return complete_graph_response


async def create_empty_graph(engine: SQLAlchemyAsyncEngine) -> Graph:
    """
    Create an empty graph in the database.

    This function creates an empty graph in the database using the provided engine.
    It is a placeholder for actual graph creation logic.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the database.
    """
    async with AsyncSession(engine) as session:
        async with session.begin():
            graph = Graph(
                name="New Graph",
            )
            session.add(graph)
            await session.flush()

        await session.refresh(graph)
        return graph


async def update_graph_with_nodes_and_edges(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: uuid.UUID,
    graph_update_data: Graph,
    nodes: list[Node],
    edges: list[Edge],
) -> Graph:
    """
    Atomically updates a graph's properties and replaces its nodes and edges.

    Args:
        engine (AsyncEngine): The SQLAlchemy async engine instance.
        graph_id (uuid.UUID): The UUID of the graph to update.
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
            db_graph = await session.get(Graph, graph_id)

            if not db_graph:
                raise HTTPException(
                    status_code=404, detail=f"Graph with id {graph_id} not found"
                )

            if (
                hasattr(graph_update_data, "name")
                and graph_update_data.name is not None
            ):
                db_graph.name = graph_update_data.name
            if (
                hasattr(graph_update_data, "description")
                and graph_update_data.description is not None
            ):
                db_graph.description = graph_update_data.description

            delete_edges_stmt = delete(Edge).where(Edge.graph_id == graph_id)
            await session.exec(delete_edges_stmt)

            delete_nodes_stmt = delete(Node).where(Node.graph_id == graph_id)
            await session.exec(delete_nodes_stmt)

            if nodes:
                for node in nodes:
                    node.graph_id = graph_id
                session.add_all(nodes)

            if edges:
                for edge in edges:
                    edge.graph_id = graph_id
                session.add_all(edges)

            # --- Opérations Neo4j (Toujours DANS la transaction PG) ---
            try:
                graph_id_str = str(graph_id)
                await update_neo4j_graph(neo4j_driver, graph_id_str, nodes, edges)

            except (Neo4jError, Exception) as e:
                print(f"Neo4j operation failed, triggering PostgreSQL rollback: {e}")
                raise e

        await session.refresh(db_graph)
        return db_graph


async def get_nodes_by_ids(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: uuid.UUID, node_ids: list[str]
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
        stmt = (
            select(Node).where(Node.graph_id == graph_id).where(Node.id.in_(node_ids))
        )
        result = await session.exec(stmt)
        nodes_found = result.scalars().all()

        nodes_map = {str(node.id): node for node in nodes_found}

        ordered_nodes = [
            nodes_map[node_id] for node_id in node_ids if node_id in nodes_map
        ]

        return ordered_nodes


async def update_graph_name(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: uuid.UUID, new_name: str
) -> Graph:
    """
    Update the name of a graph in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        graph_id (uuid.UUID): The UUID of the graph to update.
        new_name (str): The new name for the graph.

    Returns:
        Graph: The updated Graph object.

    Raises:
        HTTPException: Status 404 if the graph with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            db_graph = await session.get(Graph, graph_id)

            if not db_graph:
                raise HTTPException(
                    status_code=404, detail=f"Graph with id {graph_id} not found"
                )

            db_graph.name = new_name
            await session.commit()
            return db_graph


async def delete_graph(
    pg_engine: SQLAlchemyAsyncEngine, neo4j_driver: AsyncDriver, graph_id: uuid.UUID
) -> None:
    """
    Delete a graph and its associated nodes and edges from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        neo4j_driver (AsyncDriver): The Neo4j driver instance.
        graph_id (uuid.UUID): The UUID of the graph to delete.

    Raises:
        HTTPException: Status 404 if the graph with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            db_graph = await session.get(Graph, graph_id)

            if not db_graph:
                raise HTTPException(
                    status_code=404, detail=f"Graph with id {graph_id} not found"
                )

            try:
                await update_neo4j_graph(neo4j_driver, str(graph_id), [], [])
            except Neo4jError as e:
                print(f"Failed to delete Neo4j nodes and edges: {e}")
                raise e

            delete_edges_stmt = delete(Edge).where(Edge.graph_id == graph_id)
            await session.exec(delete_edges_stmt)

            delete_nodes_stmt = delete(Node).where(Node.graph_id == graph_id)
            await session.exec(delete_nodes_stmt)

            await session.delete(db_graph)
