from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
import uuid
from pydantic import BaseModel


from database.models import Graph, Node, Edge


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
        stmt = select(Graph)
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
    engine: SQLAlchemyAsyncEngine,
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
    async with AsyncSession(engine) as session:
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

            await session.flush()

        await session.refresh(db_graph)

        return db_graph
