from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from models.chatDTO import GenerateRequest
from pydantic import BaseModel
from services.auth import get_current_user_id
from services.graph_service import (
    ExecutionPlanResponse,
    Message,
    construct_message_history,
    get_execution_plan_by_node,
)
from services.stream import (
    handle_chat_completion_stream,
    handle_parallelization_aggregator_stream,
    handle_routing_stream,
)
from services.stream_manager import stream_manager

router = APIRouter()


@router.post("/chat/generate")
async def generate_stream_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    request_data: GenerateRequest,
    user_id: str = Depends(get_current_user_id),
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

    return await handle_chat_completion_stream(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        background_tasks=background_tasks,
        request_data=request_data,
        user_id=user_id,
    )


@router.post("/chat/generate/parallelization/aggregate")
async def generate_stream_endpoint_parallelization_aggregate(
    request: Request,
    background_tasks: BackgroundTasks,
    request_data: GenerateRequest,
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """
    Handles a streaming endpoint for generating responses using parallelization aggregation.

    This asynchronous endpoint constructs a prompt for a parallelization aggregator based on the
    provided request data,
    then streams the response from the OpenRouter API using the specified model and reasoning.

    Args:
        request (Request): The incoming HTTP request object, containing application state and
            dependencies.
        request_data (GenerateRequest): The data required to generate the prompt and configure
            the model, including graph and node identifiers, system prompt, model name,
            and reasoning parameters.

    Returns:
        StreamingResponse: A streaming HTTP response that yields the generated text in plain
            text format.
    """

    return await handle_parallelization_aggregator_stream(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        background_tasks=background_tasks,
        request_data=request_data,
        user_id=user_id,
    )


@router.post("/chat/generate/routing")
async def generate_stream_endpoint_routing(
    request: Request,
    background_tasks: BackgroundTasks,
    request_data: GenerateRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """
    Handles an endpoint for generating routing decisions based on user queries.

    Args:
        request (Request): The incoming HTTP request object, containing application state and
            dependencies.
        request_data (GenerateRequest): The data required to generate the prompt and configure
            the model, including graph and node identifiers, system prompt, model name,
            and reasoning parameters.

    Returns:
        dict: A dictionary containing the routing decision in JSON format.
    """
    return await handle_routing_stream(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        background_tasks=background_tasks,
        request_data=request_data,
        user_id=user_id,
    )


class CancelResponse(BaseModel):
    cancelled: bool


@router.post("/chat/{graph_id}/{node_id}/cancel")
async def cancel_stream(
    graph_id: str,
    node_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> CancelResponse:
    """
    Cancels an ongoing stream for a specific graph and node.

    Args:
        graph_id (str): The ID of the graph.
        node_id (str): The ID of the node.
        request (Request): The FastAPI request object containing application state.

    Returns:
        CancelResponse: A Pydantic model indicating whether the cancellation was successful.
    """
    if not graph_id or not node_id:
        raise HTTPException(status_code=400, detail="Missing graph_id or node_id")

    cancelled = stream_manager.cancel_stream(graph_id, node_id)
    return CancelResponse(cancelled=cancelled)


@router.get("/chat/{graph_id}/{node_id}/execution-plan/{direction}")
async def get_execution_plan(
    graph_id: str,
    node_id: str,
    direction: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> ExecutionPlanResponse:
    """
    Retrieves the execution plan for a specific node in a graph.

    Args:
        graph_id (str): The ID of the graph.
        node_id (str): The ID of the node.
        direction (str): The direction of the execution plan, either 'upstream' or 'downstream'.
        request (Request): The FastAPI request object containing application state.

    Returns:
        ExecutionPlanResponse: A dictionary containing the execution plan.
    """
    if direction not in ["upstream", "downstream", "all", "multiple"]:
        raise HTTPException(status_code=400, detail="Invalid direction specified")

    execution_plan = await get_execution_plan_by_node(
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=graph_id,
        node_id=node_id,
        direction=direction,
    )
    return execution_plan


@router.get("/chat/{graph_id}/{node_id}")
async def get_chat(
    request: Request,
    graph_id: str,
    node_id: str,
    user_id: str = Depends(get_current_user_id),
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
        user_id=user_id,
        node_id=node_id,
        system_prompt="",
        add_current_node=True,
        add_file_content=False,
        github_auto_pull=False,
    )

    return messages
