import logging
from typing import Optional

from database.pg.models import Graph
from fastapi import HTTPException
from models.chatDTO import EffortEnum
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger("uvicorn.error")


async def update_graph_name(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: str, new_name: str
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

            if not isinstance(db_graph, Graph):
                raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

            return db_graph


async def toggle_graph_pin(pg_engine: SQLAlchemyAsyncEngine, graph_id: str, pinned: bool) -> Graph:
    """
    Pin or unpin a graph in the database.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy async engine instance.
        graph_id (uuid.UUID): The UUID of the graph to pin or unpin.
        pinned (bool): True to pin the graph, False to unpin it.

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

            db_graph.pinned = pinned
            await session.commit()

            if not isinstance(db_graph, Graph):
                raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

            return db_graph


class GraphConfigUpdate(BaseModel):
    """
    Pydantic model for updating graph configuration.
    """

    custom_instructions: list[str]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    top_k: Optional[int] = 40
    frequency_penalty: Optional[float] = 0.0
    presence_penalty: Optional[float] = 0.0
    repetition_penalty: Optional[float] = 1.0
    reasoning_effort: Optional[EffortEnum] = EffortEnum.MEDIUM
    exclude_reasoning: bool = False
    include_thinking_in_context: bool = False
    block_github_auto_pull: bool = False
    pdf_engine: str = "default"
    default_selected_tools: list[str] = []
    tools_web_search_num_results: int = 5
    tools_web_search_ignored_sites: list[str] = []
    tools_web_search_preferred_sites: list[str] = []
    tools_web_search_custom_api_key: Optional[str] = None
    tools_web_search_force_custom_api_key: bool = True
    tools_link_extraction_max_length: int = 100000


async def update_graph_config(
    pg_engine: SQLAlchemyAsyncEngine, graph_id: str, config: GraphConfigUpdate
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

            if not db_graph or not isinstance(db_graph, Graph):
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

            if not isinstance(db_graph, Graph):
                raise HTTPException(status_code=404, detail=f"Graph with id {graph_id} not found")

            return db_graph


async def get_canvas_config(pg_engine: SQLAlchemyAsyncEngine, graph_id: str) -> GraphConfigUpdate:
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
            temperature=db_graph.temperature if db_graph.temperature is not None else 0.7,
            top_p=db_graph.top_p if db_graph.top_p is not None else 1.0,
            top_k=db_graph.top_k if db_graph.top_k is not None else 40,
            frequency_penalty=(
                db_graph.frequency_penalty if db_graph.frequency_penalty is not None else 0.0
            ),
            presence_penalty=(
                db_graph.presence_penalty if db_graph.presence_penalty is not None else 0.0
            ),
            repetition_penalty=(
                db_graph.repetition_penalty if db_graph.repetition_penalty is not None else 1.0
            ),
            reasoning_effort=(
                EffortEnum(db_graph.reasoning_effort)
                if db_graph.reasoning_effort
                else EffortEnum.MEDIUM
            ),
        )
