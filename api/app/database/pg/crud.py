from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from pydantic import BaseModel, Field
from neo4j import AsyncDriver
from neo4j.exceptions import Neo4jError
import logging
import uuid

from database.pg.models import Graph, Node, Edge, User, Settings, Files
from database.neo4j.crud import update_neo4j_graph
from models.auth import ProviderEnum
from models.chatDTO import EffortEnum

logger = logging.getLogger("uvicorn.error")


class CompleteGraph(BaseModel):
    graph: Graph
    nodes: list[Node]
    edges: list[Edge]


async def get_all_graphs(
    engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> list[Graph]:
    """
    Retrieve all graphs from the database.

    This function retrieves all graphs from the database using the provided engine.

    Args:
        engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance connected to the database.

    Returns:
        list[Graph]: A list of Graph objects.
    """
    async with AsyncSession(engine) as session:
        # Create a subquery to count nodes for each graph_id
        node_count_subquery = (
            select(Node.graph_id, func.count(Node.id).label("node_count"))
            .group_by(Node.graph_id)
            .subquery()
        )

        # Main query to select Graph and the node_count from the subquery
        stmt = (
            select(Graph, node_count_subquery.c.node_count)
            .outerjoin(node_count_subquery, Graph.id == node_count_subquery.c.graph_id)
            .where(Graph.user_id == user_id)
            .order_by(Graph.updated_at.desc())
        )

        result = await session.exec(stmt)

        graphs = []
        for graph, count in result.all():
            graph.node_count = count or 0
            graphs.append(graph)

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

        complete_graph_response = CompleteGraph(
            graph=db_graph,
            nodes=db_graph.nodes,
            edges=db_graph.edges,
        )

        return complete_graph_response


async def create_empty_graph(
    engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> Graph:
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
                name="New Canvas",
                user_id=user_id,
            )
            session.add(graph)
            await session.flush()

        await session.refresh(graph)
        return graph


async def update_graph_with_nodes_and_edges(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: uuid.UUID,
    user_id: uuid.UUID,
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
            # Fetch the graph using a locking select to ensure no other transaction modifies it
            stmt = select(Graph).where(Graph.id == graph_id).with_for_update()
            result = await session.exec(stmt)
            db_graph = result.scalar_one_or_none()

            if db_graph:
                db_graph.updated_at = func.now()

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

            with session.no_autoflush:
                await session.exec(delete(Edge).where(Edge.graph_id == graph_id))
                await session.exec(delete(Node).where(Node.graph_id == graph_id))

            await session.flush()

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
                logger.error(
                    f"Neo4j operation failed, triggering PostgreSQL rollback: {e}"
                )
                raise e

        await session.refresh(db_graph, attribute_names=["nodes", "edges"])
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


class GraphConfigUpdate(BaseModel):
    """
    Pydantic model for updating graph configuration.
    """

    custom_instructions: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    repetition_penalty: float | None = None
    reasoning_effort: EffortEnum | None = None
    exclude_reasoning: bool = False


async def update_graph_config(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: uuid.UUID, config: GraphConfigUpdate
) -> Graph:
    """
    Update the configuration of a graph in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        graph_id (uuid.UUID): The UUID of the graph to update.
        config (dict): The new configuration for the graph.

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

            # Update the graph configuration fields
            db_graph.custom_instructions = config.custom_instructions
            db_graph.max_tokens = config.max_tokens
            db_graph.temperature = config.temperature
            db_graph.top_p = config.top_p
            db_graph.top_k = config.top_k
            db_graph.frequency_penalty = config.frequency_penalty
            db_graph.presence_penalty = config.presence_penalty
            db_graph.repetition_penalty = config.repetition_penalty
            db_graph.reasoning_effort = config.reasoning_effort

            await session.commit()
            return db_graph


async def get_canvas_config(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: uuid.UUID
) -> GraphConfigUpdate:
    """
    Retrieve the configuration of a graph from the database.
    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        graph_id (uuid.UUID): The UUID of the graph to retrieve the configuration for.
    Returns:
        GraphConfigUpdate: A Pydantic model containing the graph's configuration.
    Raises:
        HTTPException: Status 404 if the graph with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        db_graph = await session.get(Graph, graph_id)

        if not db_graph:
            raise HTTPException(
                status_code=404, detail=f"Graph with id {graph_id} not found"
            )

        return GraphConfigUpdate(
            custom_instructions=db_graph.custom_instructions,
            max_tokens=db_graph.max_tokens,
            temperature=db_graph.temperature,
            top_p=db_graph.top_p,
            top_k=db_graph.top_k,
            frequency_penalty=db_graph.frequency_penalty,
            presence_penalty=db_graph.presence_penalty,
            repetition_penalty=db_graph.repetition_penalty,
            reasoning_effort=db_graph.reasoning_effort,
        )


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
                logger.error(f"Failed to delete Neo4j nodes and edges: {e}")
                raise e

            delete_edges_stmt = delete(Edge).where(Edge.graph_id == graph_id)
            await session.exec(delete_edges_stmt)

            delete_nodes_stmt = delete(Node).where(Node.graph_id == graph_id)
            await session.exec(delete_nodes_stmt)

            await session.delete(db_graph)


class ProviderUserPayload(BaseModel):
    oauth_id: int = Field(..., alias="oauthId")
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = Field(None, alias="avatarUrl")
    password: str | None = None


async def create_user_from_provider(
    pg_engine: SQLAlchemyAsyncEngine,
    payload: ProviderUserPayload,
    provider: ProviderEnum,
) -> User:
    """
    Create a new user in the database from OAuth provider data.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        payload (ProviderUserPayload): The payload containing user data from the OAuth provider.
        provider (str): The name of the OAuth provider (e.g., "github", "google").

    Returns:
        User: The newly created User object.

    Raises:
        HTTPException: If a user with the same OAuth ID already exists.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        async with session.begin():
            existing_user = await get_user_by_provider_id(
                pg_engine, str(payload.oauth_id), provider
            )

            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail=f"User with Provider ID {payload.oauth_id} already exists",
                )

            user = User(
                username=payload.name or f"user_{payload.oauth_id}",
                email=payload.email,
                avatar_url=payload.avatar_url,
                oauth_provider=provider,
                oauth_id=str(payload.oauth_id),
            )
            session.add(user)
            await session.commit()
            return user


async def get_user_by_provider_id(
    pg_engine: SQLAlchemyAsyncEngine, oauth_id: str, provider: ProviderEnum
) -> User:
    """
    Retrieve a user by their OAuth ID and provider from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        oauth_id (str): The OAuth ID of the user.
        provider (str): The name of the OAuth provider (e.g., "github", "google").

    Returns:
        User: The User object if found, otherwise None.

    Raises:
        HTTPException: Status 404 if the user with the given OAuth ID and provider is not found.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = (
            select(User)
            .where(User.oauth_id == str(oauth_id))
            .where(User.oauth_provider == provider)
        )
        result = await session.exec(stmt)
        user = result.one_or_none()

        if not user:
            return None

        return user[0]


async def get_user_by_username(
    pg_engine: SQLAlchemyAsyncEngine, username: str
) -> User | None:
    """
    Retrieve a user by their username for password-based login.
    This assumes password-based users have 'userpass' as their provider.
    """
    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        stmt = (
            select(User)
            .where(User.username == username)
            .where(User.oauth_provider == "userpass")
        )
        result = await session.exec(stmt)
        user_row = result.one_or_none()

        return user_row[0] if user_row else None


async def create_userpass_user(
    pg_engine: SQLAlchemyAsyncEngine,
    username: str,
    password: str,
    email: str | None = None,
) -> User:
    """
    Create a new user with username and password for password-based authentication.
    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        username (str): The username for the new user.
        password (str): The password for the new user.
        email (str | None): The email address for the new user, optional.
    Returns:
        User: The newly created User object.
    Raises:
        HTTPException: If a user with the same username already exists.
    """

    async with AsyncSession(pg_engine, expire_on_commit=False) as session:
        async with session.begin():
            existing_user = await get_user_by_username(pg_engine, username)

            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail=f"User with username {username} already exists",
                )

            user = User(
                username=username,
                email=email,
                oauth_provider="userpass",
                password=password,
            )
            session.add(user)
            await session.commit()
            return user


async def update_settings(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID, settings_data: dict
) -> User:
    """
    Update user settings in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user whose settings are to be updated.
        settings_data (dict): A dictionary containing the settings to update.

    Returns:
        User: The updated User object.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            user = await session.get(User, user_id)

            if not user:
                raise HTTPException(
                    status_code=404, detail=f"User with id {user_id} not found"
                )

            # Update or create settings for the user
            stmt = select(Settings).where(Settings.user_id == user_id)
            result = await session.exec(stmt)
            settings_row = result.one_or_none()

            if not settings_row:
                settings = Settings(user_id=user_id)
                session.add(settings)
            else:
                settings = settings_row[0]

            settings.settings_data = settings_data
            await session.commit()

            return user


async def get_settings(
    pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID
) -> Settings:
    """
    Retrieve user settings from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user whose settings are to be retrieved.

    Returns:
        Settings: The Settings object containing the user's settings.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(Settings).where(Settings.user_id == user_id)
        result = await session.exec(stmt)
        settings = result.one_or_none()

        if not settings:
            raise HTTPException(
                status_code=404, detail=f"Settings for user {user_id} not found"
            )

        return settings[0]


async def does_user_exist(pg_engine: SQLAlchemyAsyncEngine, user_id: uuid.UUID) -> bool:
    """
    Check if a user exists in the database by their ID.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user to check.

    Returns:
        bool: True if the user exists, False otherwise.
    """
    async with AsyncSession(pg_engine) as session:
        stmt = select(User).where(User.id == user_id)
        result = await session.exec(stmt)
        return result.one_or_none() is not None


async def add_user_file(
    pg_engine: SQLAlchemyAsyncEngine,
    id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    file_path: str,
    size: int,
    content_type: str,
) -> None:
    """
    Add a file path to the user's files in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        user_id (uuid.UUID): The UUID of the user to whom the file belongs.
        file_path (str): The path of the file to add.

    Raises:
        HTTPException: Status 404 if the user with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        async with session.begin():
            user = await session.get(User, user_id)

            if not user:
                raise HTTPException(
                    status_code=404, detail=f"User with id {user_id} not found"
                )

            file_record = Files(
                id=id,
                user_id=user_id,
                filename=filename,
                file_path=file_path,
                size=size,
                content_type=content_type,
            )
            session.add(file_record)
            await session.commit()


async def get_file_by_id(pg_engine: SQLAlchemyAsyncEngine, file_id: uuid.UUID) -> Files:
    """
    Retrieve a file by its ID from the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        file_id (uuid.UUID): The UUID of the file to retrieve.

    Returns:
        Files: The Files object if found, otherwise None.

    Raises:
        HTTPException: Status 404 if the file with the given ID is not found.
    """
    async with AsyncSession(pg_engine) as session:
        file_record = await session.get(Files, file_id)

        if not file_record:
            raise HTTPException(
                status_code=404, detail=f"File with id {file_id} not found"
            )

        return file_record
