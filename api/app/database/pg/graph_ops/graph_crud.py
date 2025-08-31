import logging

from database.neo4j.crud import update_neo4j_graph
from database.pg.models import Edge, Graph, Node
from fastapi import HTTPException
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlalchemy.orm import selectinload
from sqlmodel import and_
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def get_all_graphs(engine: SQLAlchemyAsyncEngine, user_id: str) -> list[Graph]:
    """
    Retrieve all graphs from the database.

    This function retrieves all graphs from the database using the provided engine.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected
            to the database.

    Returns:
        list[Graph]: A list of Graph objects.
    """
    async with AsyncSession(engine) as session:
        # Create a subquery to count nodes for each graph_id
        node_count_subquery = (
            select(Node.graph_id, func.count(Node.id).label("node_count"))  # type: ignore
            .group_by(Node.graph_id)
            .subquery()
        )

        # Main query to select Graph and the node_count from the subquery
        stmt = (
            select(Graph, node_count_subquery.c.node_count)
            .outerjoin(node_count_subquery, Graph.id == node_count_subquery.c.graph_id)
            .where(and_(Graph.user_id == user_id))
            .order_by(func.coalesce(Graph.updated_at, func.now()).desc())
        )

        result = await session.exec(stmt)  # type: ignore

        graphs = []
        for graph, count in result.all():
            graph.node_count = count or 0
            graphs.append(graph)

        return graphs


class CompleteGraph(BaseModel):
    graph: Graph
    nodes: list[Node]
    edges: list[Edge]


async def get_graph_by_id(engine: SQLAlchemyAsyncEngine, graph_id: str) -> CompleteGraph:
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
        options = [selectinload(Graph.nodes), selectinload(Graph.edges)]  # type: ignore
        db_graph = await session.get(Graph, graph_id, options=options)

        if not db_graph:
            raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

        complete_graph_response = CompleteGraph(
            graph=db_graph,
            nodes=db_graph.nodes,
            edges=db_graph.edges,
        )

        return complete_graph_response


async def create_empty_graph(engine: SQLAlchemyAsyncEngine, user_id: str) -> Graph:
    """
    Create an empty graph in the database.

    This function creates an empty graph in the database using the provided engine.
    It is a placeholder for actual graph creation logic.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the
            database.
    """
    async with AsyncSession(engine) as session:
        async with session.begin():
            graph = Graph(
                name="New Canvas",
                user_id=user_id,
            )
            session.add(graph)
            await session.flush()

        await session.refresh(graph)
        return graph


async def delete_graph(
    pg_engine: SQLAlchemyAsyncEngine, neo4j_driver: AsyncDriver, graph_id: str
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
                raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

            try:
                await update_neo4j_graph(neo4j_driver, str(graph_id), [], [])
            except Neo4jError as e:
                logger.error(f"Failed to delete Neo4j nodes and edges: {e}")
                raise e

            delete_edges_stmt = delete(Edge).where(and_(Edge.graph_id == graph_id))
            await session.exec(delete_edges_stmt)  # type: ignore

            delete_nodes_stmt = delete(Node).where(and_(Node.graph_id == graph_id))
            await session.exec(delete_nodes_stmt)  # type: ignore

            await session.delete(db_graph)
