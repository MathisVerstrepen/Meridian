import logging
from datetime import datetime, timedelta, timezone

from database.neo4j.crud import update_neo4j_graph
from database.pg.models import Edge, Graph, Node
from fastapi import HTTPException
from models.usersDTO import SettingsDTO
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

        # Main query to select the Graph object and the node_count as separate columns
        stmt = (
            select(Graph, node_count_subquery.c.node_count)
            .outerjoin(node_count_subquery, Graph.id == node_count_subquery.c.graph_id)
            .where(and_(Graph.user_id == user_id, Graph.temporary == False))  # noqa: E712
            .order_by(func.coalesce(Graph.updated_at, func.now()).desc())
        )

        result = await session.exec(stmt)  # type: ignore

        # Manually process the results and assign the count to the property
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

        db_graph.node_count = len(db_graph.nodes)

        complete_graph_response = CompleteGraph(
            graph=db_graph,
            nodes=db_graph.nodes,
            edges=db_graph.edges,
        )

        return complete_graph_response


async def create_empty_graph(
    engine: SQLAlchemyAsyncEngine, user_id: str, user_config: SettingsDTO, temporary: bool
) -> Graph:
    """
    Create an empty graph in the database.

    This function creates an empty graph in the database using the provided engine.
    It is a placeholder for actual graph creation logic.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the
            database.
    """
    systemPromptSelected = [sp.id for sp in user_config.models.systemPrompt if sp.enabled]

    async with AsyncSession(engine) as session:
        async with session.begin():
            graph = Graph(
                name="New Canvas",
                user_id=user_id,
                temporary=temporary,
                custom_instructions=systemPromptSelected,
                max_tokens=user_config.models.maxTokens,
                temperature=user_config.models.temperature,
                top_p=user_config.models.topP,
                top_k=user_config.models.topK,
                frequency_penalty=user_config.models.frequencyPenalty,
                presence_penalty=user_config.models.presencePenalty,
                repetition_penalty=user_config.models.repetitionPenalty,
                reasoning_effort=user_config.models.reasoningEffort,
            )
            session.add(graph)
            await session.flush()

        await session.refresh(graph)
        return graph


async def persist_temporary_graph(
    engine: SQLAlchemyAsyncEngine, graph_id: str, user_id: str
) -> Graph:
    """
    Persists a temporary graph by setting its 'temporary' flag to False.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine.
        graph_id (str): The ID of the graph to persist.
        user_id (str): The ID of the user who owns the graph.

    Returns:
        Graph: The updated, now permanent, Graph object.

    Raises:
        HTTPException: If the graph is not found or does not belong to the user.
    """
    async with AsyncSession(engine) as session:
        async with session.begin():
            stmt = select(Graph).where(and_(Graph.id == graph_id, Graph.user_id == user_id))
            result = await session.exec(stmt)  # type: ignore
            db_graph = result.scalar_one_or_none()

            if not db_graph:
                raise HTTPException(
                    status_code=404,
                    detail=f"Graph with id {graph_id} not found for this user.",
                )

            if db_graph.temporary:
                db_graph.temporary = False
                session.add(db_graph)

        await session.refresh(db_graph)
        if not isinstance(db_graph, Graph):
            raise HTTPException(
                status_code=500, detail="Unexpected error: Retrieved object is not of type Graph."
            )

        await session.refresh(db_graph, attribute_names=["nodes", "edges"])

        db_graph.node_count = len(db_graph.nodes)

        return db_graph


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


async def delete_old_temporary_graphs(
    pg_engine: SQLAlchemyAsyncEngine, neo4j_driver: AsyncDriver
) -> None:
    """
    Deletes temporary graphs that have not been updated for more than an hour.
    """
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    graph_ids_to_delete: list[str] = []

    async with AsyncSession(pg_engine) as session:
        stmt = select(Graph.id).where(  # type: ignore
            and_(
                Graph.temporary == True,  # noqa: E712
                Graph.updated_at < one_hour_ago,  # type: ignore
            )
        )
        result = await session.execute(stmt)
        graph_ids_to_delete = list(map(str, result.scalars().all()))

    if not graph_ids_to_delete:
        return

    logger.info(f"Cron job: Found {len(graph_ids_to_delete)} old temporary graphs to delete.")

    # Neo4j deletion
    for graph_id in graph_ids_to_delete:
        try:
            await update_neo4j_graph(neo4j_driver, str(graph_id), [], [])
        except Neo4jError as e:
            logger.error(f"Cron job: Failed to delete Neo4j data for graph {graph_id}: {e}")

    # PG bulk deletion
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            delete_edges_stmt = delete(Edge).where(
                Edge.graph_id.in_(graph_ids_to_delete)  # type: ignore
            )
            await session.exec(delete_edges_stmt)  # type: ignore

            delete_nodes_stmt = delete(Node).where(
                Node.graph_id.in_(graph_ids_to_delete)  # type: ignore
            )
            await session.exec(delete_nodes_stmt)  # type: ignore

            delete_graphs_stmt = delete(Graph).where(
                Graph.id.in_(graph_ids_to_delete)  # type: ignore
            )
            await session.exec(delete_graphs_stmt)  # type: ignore

    logger.info(
        f"Cron job: Successfully deleted {len(graph_ids_to_delete)} "
        f"temporary graphs from PostgreSQL."
    )
