import httpx
from const.prompts import TITLE_GENERATION_PROMPT
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
from models.chatDTO import GenerateRequest
from models.message import MessageContentTypeEnum, NodeTypeEnum
from neo4j import AsyncDriver
from services.graph_service import (
    construct_message_history,
    construct_parallelization_aggregator_prompt,
    construct_routing_prompt,
    get_effective_graph_config,
)
from services.node import CleanTextOption, get_first_user_prompt, system_message_builder
from services.openrouter import (
    OpenRouterReqChat,
    stream_openrouter_response,
    make_openrouter_request_non_streaming,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine


async def handle_chat_completion_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    background_tasks: BackgroundTasks,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
) -> StreamingResponse:
    """
    Handles chat completion requests by streaming the generated text.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy engine for PostgreSQL.
        neo4j_driver (AsyncDriver): The Neo4j driver for database interactions.
        request_data (GenerateRequest): The request data containing graph_id, node_id, and model.
        user_id (str): The user ID from the request headers.

    Returns:
        StreamingResponse: A streaming HTTP response that yields the generated text in plain text
            format.
    """

    graph_config, system_prompt, open_router_api_key = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        user_id=user_id,
    )

    messages = await construct_message_history(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=request_data.graph_id,
        user_id=user_id,
        node_id=request_data.node_id,
        system_prompt=system_prompt,
        add_current_node=False,
        clean_text=(
            CleanTextOption.REMOVE_TAGS_ONLY
            if graph_config.include_thinking_in_context
            else CleanTextOption.REMOVE_TAG_AND_TEXT
        ),
        github_auto_pull=graph_config.block_github_auto_pull,
    )

    node = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        node_ids=[request_data.node_id],
    )

    # Classic chat completion
    if not request_data.title:
        openRouterReq = OpenRouterReqChat(
            api_key=open_router_api_key,
            model=request_data.model,
            model_id=request_data.modelId,
            messages=messages,
            config=graph_config,
            node_id=request_data.node_id,
            graph_id=request_data.graph_id,
            node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
            http_client=http_client,
        )

    # Title generation
    else:
        first_prompt_node = get_first_user_prompt(messages)

        if not first_prompt_node:
            raise ValueError("No user prompt found in the messages.")

        text_content = next(
            (
                content
                for content in first_prompt_node.content
                if content.type == MessageContentTypeEnum.text
            ),
            None,
        )

        # Truncate text_content.text if it exceeds 2000 characters
        if (
            text_content
            and text_content.text
            and hasattr(text_content, MessageContentTypeEnum.text)
            and len(text_content.text) > 2000
        ):
            text_content.text = f"{text_content.text[:1000]}...{text_content.text[-1000:]}"

        first_prompt_node.content = [text_content] if text_content else []

        graph_config.max_tokens = 50

        system_msg = system_message_builder(TITLE_GENERATION_PROMPT)
        messages = [system_msg] if system_msg is not None else []
        messages.append(first_prompt_node)

        openRouterReq = OpenRouterReqChat(
            api_key=open_router_api_key,
            model="deepseek/deepseek-chat-v3-0324",
            messages=messages,
            config=graph_config,
            node_id=request_data.node_id,
            graph_id=request_data.graph_id,
            is_title_generation=True,
            node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
        )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq, pg_engine, background_tasks),
        media_type="text/plain",
    )


async def handle_parallelization_aggregator_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    background_tasks: BackgroundTasks,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
) -> StreamingResponse:
    """
    Handles parallelization aggregator requests by streaming the generated text.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy engine for PostgreSQL.
        neo4j_driver (AsyncDriver): The Neo4j driver for database interactions.
        request_data (GenerateRequest): The request data containing graph_id, node_id, and model.
        user_id (str): The user ID from the request headers.

    Returns:
        StreamingResponse: A streaming HTTP response that yields the generated text in plain
            text format.
    """

    graph_config, system_prompt, open_router_api_key = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        user_id=user_id,
    )

    messages = await construct_parallelization_aggregator_prompt(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=request_data.graph_id,
        user_id=user_id,
        node_id=request_data.node_id,
        system_prompt=system_prompt,
        github_auto_pull=graph_config.block_github_auto_pull,
    )

    node = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        node_ids=[request_data.node_id],
    )

    openRouterReq = OpenRouterReqChat(
        api_key=open_router_api_key,
        model=request_data.model,
        messages=messages,
        config=graph_config,
        node_id=request_data.node_id,
        graph_id=request_data.graph_id,
        is_title_generation=False,
        node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
        http_client=http_client,
    )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq, pg_engine, background_tasks),
        media_type="text/plain",
    )


async def handle_routing_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    background_tasks: BackgroundTasks,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
) -> dict:
    """
    Handles routing requests by streaming the generated text.

    Args:
        pg_engine (SQLAlchemyAsyncEngine): The SQLAlchemy engine for PostgreSQL.
        neo4j_driver (AsyncDriver): The Neo4j driver for database interactions.
        request_data (GenerateRequest): The request data containing graph_id, node_id, and model.
        user_id (str): The user ID from the request headers.

    Returns:
        StreamingResponse: A streaming HTTP response that yields the generated text in plain
            text format.
    """

    graph_config, _, open_router_api_key = await get_effective_graph_config(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        user_id=user_id,
    )

    messages, schema = await construct_routing_prompt(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=request_data.graph_id,
        node_id=request_data.node_id,
        user_id=user_id,
    )

    node = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        node_ids=[request_data.node_id],
    )

    openRouterReq = OpenRouterReqChat(
        api_key=open_router_api_key,
        model="deepseek/deepseek-chat-v3-0324",
        messages=messages,
        config=graph_config,
        node_id=request_data.node_id,
        graph_id=request_data.graph_id,
        is_title_generation=False,
        node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
        schema=schema,
        stream=False,
        http_client=http_client,
    )

    full_response = await make_openrouter_request_non_streaming(
        openRouterReq, pg_engine, background_tasks
    )

    return schema.model_validate_json(full_response).model_dump()
