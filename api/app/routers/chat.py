from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from enum import Enum

from services.openrouter import stream_openrouter_response, OpenRouterReqChat
from services.graph_service import (
    construct_message_history,
    construct_parallelization_aggregator_prompt,
    Message,
)
from database.pg.crud import get_graph_config

router = APIRouter()


class EffortEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# https://openrouter.ai/docs/use-cases/reasoning-tokens
class Reasoning(BaseModel):
    effort: EffortEnum = EffortEnum.MEDIUM
    exclude: bool = False


class GenerateRequest(BaseModel):
    graph_id: str
    node_id: str
    model: str
    reasoning: Reasoning
    system_prompt: str = ""


@router.post("/chat/generate")
async def generate_stream_endpoint(
    request: Request, request_data: GenerateRequest
) -> StreamingResponse:
    """
    Handles a streaming chat generation request.

    This endpoint constructs a prompt based on the graph context and streams back the response
    from the OpenRouter API.

    Args:
        request (Request): The FastAPI request object containing application state.
        request_data (GenerateRequest): The request data containing graph_id, node_id and model.

    Returns:
        StreamingResponse: A streaming response with plain text content from the AI model.

    Raises:
        HTTPException: If there are issues with the graph_id, node_id, or API connection.
    """

    # TODO: fetch config also from global config table
    config = await get_graph_config(
        pg_engine=request.app.state.pg_engine,
        graph_id=request_data.graph_id,
    )

    messages = await construct_message_history(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=request_data.graph_id,
        node_id=request_data.node_id,
        system_prompt=config.custom_instructions or request_data.system_prompt,
    )

    openRouterReq = OpenRouterReqChat(
        api_key=request.app.state.open_router_api_key,
        model=request_data.model,
        messages=messages,
        config=config,
        reasoning=request_data.reasoning.model_dump(),
    )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq),
        media_type="text/plain",
    )


@router.post("/chat/generate/parallelization/aggregate")
async def generate_stream_endpoint_parallelization_aggregate(
    request: Request, request_data: GenerateRequest
) -> StreamingResponse:
    """
    Handles a streaming endpoint for generating responses using parallelization aggregation.

    This asynchronous endpoint constructs a prompt for a parallelization aggregator based on the provided request data,
    then streams the response from the OpenRouter API using the specified model and reasoning.

    Args:
        request (Request): The incoming HTTP request object, containing application state and dependencies.
        request_data (GenerateRequest): The data required to generate the prompt and configure the model, including
            graph and node identifiers, system prompt, model name, and reasoning parameters.

    Returns:
        StreamingResponse: A streaming HTTP response that yields the generated text in plain text format.
    """
    config = await get_graph_config(
        pg_engine=request.app.state.pg_engine,
        graph_id=request_data.graph_id,
    )

    messages = await construct_parallelization_aggregator_prompt(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=request_data.graph_id,
        node_id=request_data.node_id,
        system_prompt=config.custom_instructions or request_data.system_prompt,
    )

    openRouterReq = OpenRouterReqChat(
        api_key=request.app.state.open_router_api_key,
        model=request_data.model,
        messages=messages,
        config=config,
        reasoning=request_data.reasoning.model_dump(),
    )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq),
        media_type="text/plain",
    )


@router.get("/chat/{graph_id}/{node_id}")
async def get_chat(
    request: Request,
    graph_id: str,
    node_id: str,
) -> list[Message]:
    """
    Retrieves the chat history for a specific node in a graph.

    Args:
        request (Request): The FastAPI request object containing application state.
        graph_id (str): The ID of the graph.
        node_id (str): The ID of the node.
    """
    messages = await construct_message_history(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        system_prompt="",
        add_current_node=True,
    )

    return messages
