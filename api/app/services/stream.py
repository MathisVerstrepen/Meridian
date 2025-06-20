from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from neo4j import AsyncDriver

from fastapi.responses import StreamingResponse

from services.openrouter import stream_openrouter_response, OpenRouterReqChat
from services.graph_service import (
    construct_message_history,
    get_effective_graph_config,
)
from services.node import system_message_builder, get_first_user_prompt
from models.chatDTO import GenerateRequest


async def handle_chat_completion_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    request_data: GenerateRequest,
    user_id: str,
) -> StreamingResponse:
    """
    Handles chat completion requests by streaming the generated text.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy engine for PostgreSQL.
        neo4j_driver (AsyncDriver): The Neo4j driver for database interactions.
        request_data (GenerateRequest): The request data containing graph_id, node_id, and model.
        user_id (str): The user ID from the request headers.

    Returns:
        StreamingResponse: A streaming HTTP response that yields the generated text in plain text format.
    """

    graph_config, open_router_api_key = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        user_id=user_id,
    )

    messages = await construct_message_history(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=request_data.graph_id,
        node_id=request_data.node_id,
        system_prompt=graph_config.custom_instructions,
    )

    # Classic chat completion
    if not request_data.title:
        openRouterReq = OpenRouterReqChat(
            api_key=open_router_api_key,
            model=request_data.model,
            messages=messages,
            config=graph_config,
        )

    # Title generation
    else:
        first_prompt_node = get_first_user_prompt(messages)

        if not first_prompt_node:
            raise ValueError("No user prompt found in the messages.")

        openRouterReq = OpenRouterReqChat(
            api_key=open_router_api_key,
            model="google/gemini-2.5-flash-preview-05-20",
            messages=[
                system_message_builder(
                    """
                    You are a helpful assistant that generates titles for chat conversations.
                    The title should be concise and reflect the main topic of the conversation.
                    Use the following conversation to generate a suitable title.
                    Titles should not be a question, but rather a statement summarizing the conversation.
                    DO NOT ANSWER THE USER PROMPT, JUST GENERATE A TITLE. MAXIMUM 10 WORDS.
                    """,
                ),
                first_prompt_node,
            ],
            config=graph_config,
        )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq, include_usage=not request_data.title),
        media_type="text/plain",
    )
