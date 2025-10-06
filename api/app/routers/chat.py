import asyncio
import logging
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from models.chatDTO import GenerateRequest
from pydantic import BaseModel
from services.auth import get_current_user_id, get_user_id_from_websocket_token
from services.graph_service import (
    ExecutionPlanResponse,
    Message,
    construct_message_history,
    get_execution_plan_by_node,
)
from services.stream import propagate_stream_to_websocket

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.websocket("/ws/chat/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...),
):
    """
    Handles all chat-related streaming via a single WebSocket connection.

    - Authenticates the user via a token in the query parameters.
    - Manages the WebSocket lifecycle.
    - Listens for incoming messages to start or cancel chat streams.
    - Spawns background tasks for AI generation and streams results back.
    """
    connection_manager = websocket.app.state.connection_manager
    pg_engine = websocket.app.state.pg_engine
    try:
        user_id = await get_user_id_from_websocket_token(pg_engine, token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await connection_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            payload = data.get("payload")

            if message_type == "start_stream":
                try:
                    request_data = GenerateRequest(**payload)
                    task = asyncio.create_task(
                        propagate_stream_to_websocket(
                            websocket=websocket,
                            pg_engine=websocket.app.state.pg_engine,
                            neo4j_driver=websocket.app.state.neo4j_driver,
                            background_tasks=BackgroundTasks(),
                            request_data=request_data,
                            user_id=user_id,
                            http_client=websocket.app.state.http_client,
                            redis_manager=websocket.app.state.redis_manager,
                        )
                    )
                    connection_manager.add_task(task, user_id, request_data.node_id)
                    # Add a callback to remove the task from the manager when it's done
                    task.add_done_callback(
                        lambda t: connection_manager.remove_task(user_id, request_data.node_id)
                    )
                except Exception as e:
                    logger.error(f"Error starting stream for node {payload.get('node_id')}: {e}")
                    await websocket.send_json(
                        {
                            "type": "stream_error",
                            "node_id": payload.get("node_id"),
                            "payload": {"message": "Invalid request payload."},
                        }
                    )

            elif message_type == "cancel_stream":
                node_id_to_cancel = payload.get("node_id")
                if node_id_to_cancel:
                    await connection_manager.cancel_task(user_id, node_id_to_cancel)
                else:
                    logger.warning("Received cancel_stream message without a node_id.")

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected.")
    except Exception as e:
        logger.error(f"An unexpected error occurred with client {client_id}: {e}", exc_info=True)
    finally:
        connection_manager.disconnect(client_id)


class CancelResponse(BaseModel):
    cancelled: bool


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
        view="reduce",
        github_auto_pull=False,
    )

    return messages
