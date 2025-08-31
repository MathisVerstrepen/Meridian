import logging
import uuid

from database.pg.models import Graph
from fastapi import HTTPException
from models.chatDTO import EffortEnum
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


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
                raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

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
    include_thinking_in_context: bool = False


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
                raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

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
            raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

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
