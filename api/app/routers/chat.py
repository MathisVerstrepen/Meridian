from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.llm_service import stream_openrouter_response, OpenRouterReq
from services.graph_service import construct_message_history, Message

router = APIRouter()


class GenerateRequest(BaseModel):
    graph_id: str
    node_id: str
    model: str


@router.post("/chat/generate")
async def generate_stream_endpoint(request: Request, request_data: GenerateRequest):
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
    messages = await construct_message_history(
        pg_engine=request.app.state.pg_engine,
        neo4j_driver=request.app.state.neo4j_driver,
        graph_id=request_data.graph_id,
        node_id=request_data.node_id,
    )

    openRouterReq = OpenRouterReq(
        api_key=request.app.state.open_router_api_key,
        model=request_data.model,
        messages=messages,
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
        add_current_node=True,
    )

    return messages