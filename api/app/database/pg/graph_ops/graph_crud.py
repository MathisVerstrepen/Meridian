import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from database.neo4j.crud import update_neo4j_graph
from database.pg.models import Edge, Folder, Graph, Node, Workspace
from fastapi import HTTPException
from models.usersDTO import SettingsDTO
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlalchemy.orm import selectinload
from sqlmodel import and_, col
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")
DEFAULT_GRAPH_PAGE_SIZE = 25


class GraphSummary(BaseModel):
    id: uuid.UUID
    name: str
    folder_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    temporary: bool
    pinned: bool
    updated_at: datetime
    node_count: int


class GraphSummaryPage(BaseModel):
    items: list[GraphSummary]
    has_more: bool
    next_offset: int | None


def _parse_uuid_or_400(raw_id: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}.") from exc


async def _get_graph_for_user(
    session: AsyncSession,
    graph_id: str,
    user_id: str,
    *,
    options: list[Any] | None = None,
    with_for_update: bool = False,
) -> Graph:
    graph_uuid = _parse_uuid_or_400(graph_id, "graph ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    stmt = select(Graph).where(and_(Graph.id == graph_uuid, Graph.user_id == user_uuid))
    if options:
        stmt = stmt.options(*options)
    if with_for_update:
        stmt = stmt.with_for_update()

    result = await session.exec(stmt)  # type: ignore
    graph = result.scalar_one_or_none()

    if not graph:
        raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

    return cast(Graph, graph)


async def _get_folder_for_user(session: AsyncSession, folder_id: str, user_id: str) -> Folder:
    folder_uuid = _parse_uuid_or_400(folder_id, "folder ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    stmt = select(Folder).where(and_(Folder.id == folder_uuid, Folder.user_id == user_uuid))
    result = await session.exec(stmt)  # type: ignore
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    return cast(Folder, folder)


async def _get_workspace_for_user(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
) -> Workspace:
    workspace_uuid = _parse_uuid_or_400(workspace_id, "workspace ID")
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    stmt = select(Workspace).where(
        and_(Workspace.id == workspace_uuid, Workspace.user_id == user_uuid)
    )
    result = await session.exec(stmt)  # type: ignore
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return cast(Workspace, workspace)


async def resolve_workspace_id_for_user(
    engine: SQLAlchemyAsyncEngine,
    user_id: str,
    workspace_id: str | None,
) -> uuid.UUID | None:
    async with AsyncSession(engine) as session:
        if workspace_id:
            workspace = await _get_workspace_for_user(session, workspace_id, user_id)
            return workspace.id

        stmt = (
            select(Workspace)
            .where(and_(Workspace.user_id == user_id))
            .order_by(Workspace.created_at)  # type: ignore
            .limit(1)
        )
        result = await session.exec(stmt)  # type: ignore
        default_workspace = result.scalars().first()

        return default_workspace.id if default_workspace else None


async def assert_graph_access(
    engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
) -> None:
    async with AsyncSession(engine) as session:
        await _get_graph_for_user(session, graph_id, user_id)


async def get_all_graphs(
    engine: SQLAlchemyAsyncEngine,
    user_id: str,
    offset: int = 0,
    limit: int = DEFAULT_GRAPH_PAGE_SIZE,
) -> GraphSummaryPage:
    """
    Retrieve a paginated list of graph summaries from the database.

    This function retrieves graph history data using the provided engine while
    selecting only the fields needed by the history UI.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected
            to the database.

    Returns:
        GraphSummaryPage: A paginated list of graph summaries.
    """
    user_uuid = _parse_uuid_or_400(user_id, "user ID")

    async with AsyncSession(engine) as session:
        # Create a subquery to count nodes for each graph_id
        node_count_subquery = (
            select(Node.graph_id, func.count(Node.id).label("node_count"))  # type: ignore
            .group_by(Node.graph_id)
            .subquery()
        )

        stmt = (
            select(
                col(Graph.id),
                col(Graph.name),
                col(Graph.folder_id),
                col(Graph.workspace_id),
                col(Graph.temporary),
                col(Graph.pinned),
                col(Graph.updated_at),
                func.coalesce(node_count_subquery.c.node_count, 0).label("node_count"),
            )
            .outerjoin(node_count_subquery, col(Graph.id) == node_count_subquery.c.graph_id)
            .where(and_(col(Graph.user_id) == user_uuid, col(Graph.temporary).is_(False)))
            .order_by(col(Graph.updated_at).desc(), col(Graph.id).desc())
            .offset(offset)
            .limit(limit + 1)
        )

        result = await session.exec(stmt)  # type: ignore
        rows = result.all()
        has_more = len(rows) > limit
        visible_rows = rows[:limit]

        items = [
            GraphSummary(
                id=graph_id,
                name=name,
                folder_id=folder_id,
                workspace_id=workspace_id,
                temporary=temporary,
                pinned=pinned,
                updated_at=updated_at,
                node_count=int(node_count),
            )
            for (
                graph_id,
                name,
                folder_id,
                workspace_id,
                temporary,
                pinned,
                updated_at,
                node_count,
            ) in visible_rows
        ]

        return GraphSummaryPage(
            items=items,
            has_more=has_more,
            next_offset=offset + len(items) if has_more else None,
        )


async def get_user_folders(engine: SQLAlchemyAsyncEngine, user_id: str) -> list[Folder]:
    """
    Retrieve all folders for a user.
    """
    async with AsyncSession(engine) as session:
        stmt = select(Folder).where(and_(Folder.user_id == user_id)).order_by(Folder.name)
        result = await session.exec(stmt)  # type: ignore
        return list(result.scalars().all())


async def create_folder(
    engine: SQLAlchemyAsyncEngine, user_id: str, name: str, workspace_id: str | None = None
) -> Folder:
    """Create a new folder."""
    async with AsyncSession(engine) as session:
        target_workspace_id = None
        if workspace_id:
            workspace = await _get_workspace_for_user(session, workspace_id, user_id)
            target_workspace_id = workspace.id

        folder = Folder(
            name=name,
            user_id=user_id,
            workspace_id=target_workspace_id,
        )
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder


async def update_folder_name(
    engine: SQLAlchemyAsyncEngine,
    folder_id: str,
    user_id: str,
    name: str,
) -> Folder:
    """Update a folder's name."""
    async with AsyncSession(engine) as session:
        folder = await _get_folder_for_user(session, folder_id, user_id)

        folder.name = name
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder


async def update_folder_color(
    engine: SQLAlchemyAsyncEngine,
    folder_id: str,
    user_id: str,
    color: str,
) -> Folder:
    """Update a folder's color."""
    async with AsyncSession(engine) as session:
        folder = await _get_folder_for_user(session, folder_id, user_id)

        folder.color = color
        session.add(folder)
        await session.commit()
        await session.refresh(folder)
        return folder


async def update_folder_workspace(
    engine: SQLAlchemyAsyncEngine,
    folder_id: str,
    workspace_id: str,
    user_id: str,
) -> Folder:
    """
    Move a folder to a different workspace.
    This also updates all graphs contained in this folder to the new workspace.
    """
    async with AsyncSession(engine) as session:
        async with session.begin():
            folder = await _get_folder_for_user(session, folder_id, user_id)
            workspace = await _get_workspace_for_user(session, workspace_id, user_id)

            folder.workspace_id = workspace.id
            session.add(folder)

            # Update contained graphs
            stmt = (
                update(Graph)
                .where(and_(Graph.folder_id == folder_id, Graph.user_id == user_id))
                .values(workspace_id=workspace.id)
            )
            await session.exec(stmt)  # type: ignore

        await session.refresh(folder)
        return folder


async def delete_folder(engine: SQLAlchemyAsyncEngine, folder_id: str, user_id: str) -> None:
    """Delete a folder. Graphs inside will have folder_id set to NULL due to ON DELETE SET NULL."""
    async with AsyncSession(engine) as session:
        folder = await _get_folder_for_user(session, folder_id, user_id)
        await session.delete(folder)
        await session.commit()


async def move_graph_to_folder(
    engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
    folder_id: str | None,
) -> Graph:
    """
    Move a graph to a specific folder (or root if folder_id is None).
    If moved to a folder, it adopts the folder's workspace.
    """
    async with AsyncSession(engine) as session:
        async with session.begin():
            graph = await _get_graph_for_user(session, graph_id, user_id)

            graph.folder_id = _parse_uuid_or_400(folder_id, "folder ID") if folder_id else None

            # If moving to a folder, update workspace_id to match the folder's workspace
            if folder_id:
                folder = await _get_folder_for_user(session, folder_id, user_id)
                graph.workspace_id = folder.workspace_id

            session.add(graph)

        await session.refresh(graph, attribute_names=["folder_id", "nodes"])
        if not isinstance(graph, Graph):
            raise HTTPException(
                status_code=500, detail="Unexpected error: Retrieved object is not of type Graph."
            )

        graph.node_count = len(graph.nodes)

        return graph


async def move_graph_to_workspace(
    engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    workspace_id: str,
    user_id: str,
) -> Graph:
    """Move a graph to a specific workspace. Removes it from any folder."""
    async with AsyncSession(engine) as session:
        async with session.begin():
            graph = await _get_graph_for_user(session, graph_id, user_id)
            workspace = await _get_workspace_for_user(session, workspace_id, user_id)

            graph.workspace_id = workspace.id
            graph.folder_id = None
            session.add(graph)

        await session.refresh(graph, attribute_names=["workspace_id", "folder_id", "nodes"])

        if not isinstance(graph, Graph):
            raise HTTPException(
                status_code=500, detail="Unexpected error: Retrieved object is not of type Graph."
            )

        graph.node_count = len(graph.nodes)

        return graph


class CompleteGraph(BaseModel):
    graph: Graph
    nodes: list[Node]
    edges: list[Edge]


async def get_graph_by_id(
    engine: SQLAlchemyAsyncEngine,
    graph_id: str,
    user_id: str,
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
        options = [selectinload(Graph.nodes), selectinload(Graph.edges)]  # type: ignore
        db_graph = await _get_graph_for_user(session, graph_id, user_id, options=options)

        db_graph.node_count = len(db_graph.nodes)

        complete_graph_response = CompleteGraph(
            graph=db_graph,
            nodes=db_graph.nodes,
            edges=db_graph.edges,
        )

        return complete_graph_response


async def create_empty_graph(
    engine: SQLAlchemyAsyncEngine,
    user_id: str,
    user_config: SettingsDTO,
    temporary: bool,
    workspace_id: str | None = None,
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
            target_workspace_id = None
            if workspace_id:
                workspace = await _get_workspace_for_user(session, workspace_id, user_id)
                target_workspace_id = workspace.id
            else:
                stmt = (
                    select(Workspace)
                    .where(and_(Workspace.user_id == user_id))
                    .order_by(Workspace.created_at)  # type: ignore
                    .limit(1)
                )
                result = await session.exec(stmt)  # type: ignore
                default_ws = result.scalars().first()
                if default_ws:
                    target_workspace_id = default_ws.id

            graph = Graph(
                name="New Canvas",
                user_id=user_id,
                temporary=temporary,
                workspace_id=target_workspace_id,
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
            db_graph = await _get_graph_for_user(session, graph_id, user_id)

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
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    user_id: str,
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
            db_graph = await _get_graph_for_user(session, graph_id, user_id)

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


async def get_user_workspaces(engine: SQLAlchemyAsyncEngine, user_id: str) -> list[Workspace]:
    """Retrieve all workspaces for a user. Create default if none exist."""
    async with AsyncSession(engine) as session:
        stmt = (
            select(Workspace)
            .where(and_(Workspace.user_id == user_id))
            .order_by(Workspace.created_at)  # type: ignore
        )
        result = await session.exec(stmt)  # type: ignore
        workspaces = list(result.scalars().all())

        return workspaces


async def create_workspace(engine: SQLAlchemyAsyncEngine, user_id: str, name: str) -> Workspace:
    async with AsyncSession(engine) as session:
        ws = Workspace(name=name, user_id=user_id)
        session.add(ws)
        await session.commit()
        await session.refresh(ws)
        return ws


async def update_workspace(
    engine: SQLAlchemyAsyncEngine,
    workspace_id: str,
    user_id: str,
    name: str,
) -> Workspace:
    async with AsyncSession(engine) as session:
        ws = await _get_workspace_for_user(session, workspace_id, user_id)

        ws.name = name
        session.add(ws)
        await session.commit()
        await session.refresh(ws)

        if not isinstance(ws, Workspace):
            raise HTTPException(
                status_code=500,
                detail="Unexpected error: Retrieved object is not of type Workspace.",
            )

        return ws


async def delete_workspace(engine: SQLAlchemyAsyncEngine, workspace_id: str, user_id: str) -> None:
    workspace_uuid = _parse_uuid_or_400(workspace_id, "workspace ID")

    async with AsyncSession(engine) as session:
        async with session.begin():
            ws = await _get_workspace_for_user(session, workspace_id, user_id)

            # Prevent deleting the last workspace
            stmt_count = (
                select(func.count())
                .select_from(Workspace)
                .where(and_(Workspace.user_id == user_id))
            )
            count = await session.scalar(stmt_count)
            if count is None or count <= 1:
                raise HTTPException(status_code=400, detail="Cannot delete the only workspace.")

            # Identify Fallback Workspace (Oldest remaining that is not the target)
            stmt_fallback = (
                select(Workspace)
                .where(and_(Workspace.user_id == user_id, Workspace.id != workspace_uuid))
                .order_by(Workspace.created_at)  # type: ignore
                .limit(1)
            )
            result_fallback = await session.exec(stmt_fallback)  # type: ignore
            fallback_ws = result_fallback.scalar_one_or_none()

            if not fallback_ws:
                raise HTTPException(
                    status_code=500, detail="Unable to identify fallback workspace."
                )

            # Migrate Folders to fallback workspace
            stmt_folders = (
                update(Folder)
                .where(and_(Folder.workspace_id == workspace_uuid))
                .values(workspace_id=fallback_ws.id)
            )
            await session.exec(stmt_folders)  # type: ignore

            # Migrate Graphs to fallback workspace
            stmt_graphs = (
                update(Graph)
                .where(and_(Graph.workspace_id == workspace_uuid))
                .values(workspace_id=fallback_ws.id)
            )
            await session.exec(stmt_graphs)  # type: ignore

            # Delete the workspace
            await session.delete(ws)
