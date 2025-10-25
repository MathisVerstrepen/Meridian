import asyncio
import logging
from typing import Any

import httpx
from const.prompts import (
    TITLE_GENERATION_PROMPT,
    TOOL_FETCH_PAGE_CONTENT_GUIDE,
    TOOL_USAGE_GUIDE_HEADER,
    TOOL_WEB_SEARCH_GUIDE,
)
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from database.pg.models import Node
from database.redis.redis_ops import RedisManager
from fastapi import WebSocket
from fastapi.responses import StreamingResponse
from models.chatDTO import GenerateRequest
from models.message import Message, MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum, ToolEnum
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
    make_openrouter_request_non_streaming,
    stream_openrouter_response,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")


async def _prepare_and_inject_cached_annotations(
    messages: list[Message], redis_manager: RedisManager, pdf_engine: str
) -> tuple[list[Message], dict[str, str]]:
    """
    Injects cached annotations using a two-level lookup (local_hash -> remote_hash -> annotation)
    and prepares a map of files that will be sent to the API.

    Args:
        messages (list[Message]): The initial list of messages.
        redis_manager (RedisManager): The Redis client manager.

    Returns:
        tuple[list[Message], dict[str, str]]: A tuple containing the updated message list and a
            dictionary mapping filenames to their local hashes for files being sent.
    """
    final_messages: list[Message] = []
    found_annotations = []
    processed_remote_hashes = set()
    files_to_send_hashes: dict[str, str] = {}  # Maps filename -> local_hash

    for msg in messages:
        final_messages.append(msg)
        if msg.role == MessageRoleEnum.user:
            for content_item in msg.content:
                if (
                    content_item.type == MessageContentTypeEnum.file
                    and (file_info := content_item.file)
                    and (local_hash := file_info.hash)
                ):
                    local_hash = f"{pdf_engine}:{local_hash}"
                    # Always track files that are part of the user message
                    files_to_send_hashes[file_info.filename] = local_hash

                    # Check cache
                    remote_hash = await redis_manager.get_remote_hash(local_hash)
                    if remote_hash and remote_hash not in processed_remote_hashes:
                        cached_annotation = await redis_manager.get_annotation(remote_hash)
                        if cached_annotation:
                            found_annotations.append(cached_annotation)
                            processed_remote_hashes.add(remote_hash)

    # Inject a single assistant message with all found annotations
    if found_annotations:
        annotation_message = Message(
            role=MessageRoleEnum.assistant,
            content=[],
            annotations=found_annotations,
        )
        # Insert it after the first user message that contains files
        for i, msg in enumerate(final_messages):
            if msg.role == MessageRoleEnum.user and any(
                c.type == MessageContentTypeEnum.file for c in msg.content
            ):
                final_messages.insert(i + 1, annotation_message)
                break

    return final_messages, files_to_send_hashes


def _toggle_tools(
    system_prompt: str,
    node: list[Node] | None,
):
    selectedTools = []
    if node and node[0].data and isinstance(node[0].data, dict):
        selectedTools = node[0].data.get("selectedTools", [])

    if len(selectedTools) == 0:
        return selectedTools, system_prompt

    system_prompt = (
        system_prompt
        + "\n"
        + TOOL_USAGE_GUIDE_HEADER.format(tool_list=", ".join([tool for tool in selectedTools]))
    )

    if ToolEnum.WEB_SEARCH in selectedTools:
        system_prompt = system_prompt + "\n" + TOOL_WEB_SEARCH_GUIDE

    if ToolEnum.LINK_EXTRACTION in selectedTools:
        system_prompt = system_prompt + "\n" + TOOL_FETCH_PAGE_CONTENT_GUIDE

    return selectedTools, system_prompt


async def propagate_stream_to_websocket(
    websocket: WebSocket,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
    redis_manager: RedisManager,
):
    """
    Handles all streaming and non-streaming generation logic for WebSocket clients.
    It differentiates the logic based on the `stream_type` in the request data.
    """
    openRouterReq = None
    try:
        # Get common configurations for the graph and user
        graph_config, system_prompt, open_router_api_key = await get_effective_graph_config(
            pg_engine=pg_engine,
            graph_id=request_data.graph_id,
            user_id=user_id,
        )

        node = await get_nodes_by_ids(
            pg_engine=pg_engine,
            graph_id=request_data.graph_id,
            node_ids=[request_data.node_id],
        )
        node_type_enum = NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT

        selectedTools, system_prompt = _toggle_tools(system_prompt, node)

        # --- Branch 1: Routing Logic (Non-streaming request-response) ---
        if request_data.stream_type == NodeTypeEnum.ROUTING:
            messages, schema = await construct_routing_prompt(
                pg_engine=pg_engine,
                neo4j_driver=neo4j_driver,
                graph_id=request_data.graph_id,
                node_id=request_data.node_id,
                user_id=user_id,
            )

            openRouterReq = OpenRouterReqChat(
                api_key=open_router_api_key,
                model="deepseek/deepseek-chat-v3-0324",
                messages=messages,
                config=graph_config,
                user_id=user_id,
                pg_engine=pg_engine,
                node_id=request_data.node_id,
                graph_id=request_data.graph_id,
                is_title_generation=False,
                node_type=node_type_enum,
                schema=schema,
                stream=False,
                http_client=http_client,
                pdf_engine=graph_config.pdf_engine,
            )

            full_response = await make_openrouter_request_non_streaming(openRouterReq, pg_engine)
            routing_result = schema.model_validate_json(full_response).model_dump()

            await websocket.send_json(
                {
                    "type": "routing_response",
                    "node_id": request_data.node_id,
                    "payload": routing_result,
                }
            )
            # Signal completion
            await websocket.send_json(
                {"type": "stream_end", "node_id": request_data.node_id, "payload": {}}
            )
            return  # End execution for routing

        # --- Branch 2: Streaming Logic (Chat, Parallelization, etc.) ---
        messages = []
        is_title_generation = (
            request_data.title and request_data.stream_type == NodeTypeEnum.TEXT_TO_TEXT
        )

        if request_data.stream_type == NodeTypeEnum.PARALLELIZATION:
            messages = await construct_parallelization_aggregator_prompt(
                pg_engine=pg_engine,
                neo4j_driver=neo4j_driver,
                graph_id=request_data.graph_id,
                user_id=user_id,
                node_id=request_data.node_id,
                system_prompt=system_prompt,
                github_auto_pull=graph_config.block_github_auto_pull,
            )
        elif (
            request_data.stream_type == NodeTypeEnum.TEXT_TO_TEXT
            or request_data.stream_type == NodeTypeEnum.PARALLELIZATION_MODELS
        ):
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
        else:
            raise ValueError(f"Unsupported stream type: {request_data.stream_type}")

        messages, file_hashes = await _prepare_and_inject_cached_annotations(
            messages, redis_manager, graph_config.pdf_engine
        )

        if not is_title_generation:
            openRouterReq = OpenRouterReqChat(
                api_key=open_router_api_key,
                model=request_data.model,
                messages=messages,
                config=graph_config,
                user_id=user_id,
                pg_engine=pg_engine,
                node_id=request_data.node_id,
                graph_id=request_data.graph_id,
                node_type=node_type_enum,
                http_client=http_client,
                file_hashes=file_hashes,
                pdf_engine=graph_config.pdf_engine,
                selected_tools=selectedTools,
            )

            final_data_container: dict[str, Any] = {}
            # Stream the response back to the client
            async for chunk in stream_openrouter_response(
                openRouterReq, pg_engine, redis_manager, final_data_container
            ):
                payload = {
                    "type": "stream_chunk",
                    "node_id": request_data.node_id,
                    "payload": chunk,
                }
                if request_data.stream_type == NodeTypeEnum.PARALLELIZATION_MODELS:
                    payload["model_id"] = request_data.modelId

                await websocket.send_json(payload)

            # After the stream is finished, send usage data if available
            if usage_data := final_data_container.get("usage_data"):
                await websocket.send_json(
                    {
                        "type": "usage_data_update",
                        "node_id": request_data.node_id,
                        "payload": usage_data,
                    }
                )

            payload = {
                "type": "stream_end",
                "node_id": request_data.node_id,
                "payload": {
                    "refresh_tool_usage": len(selectedTools) > 0,
                },
            }

            if request_data.stream_type == NodeTypeEnum.PARALLELIZATION_MODELS:
                payload["model_id"] = request_data.modelId

            await websocket.send_json(payload)

        else:  # Title generation logic
            first_prompt_node = get_first_user_prompt(messages)
            if not first_prompt_node:
                raise ValueError("No user prompt found in the messages.")
            text_content = next(
                (c for c in first_prompt_node.content if c.type == MessageContentTypeEnum.text),
                None,
            )
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
                user_id=user_id,
                pg_engine=pg_engine,
                node_id=request_data.node_id,
                graph_id=request_data.graph_id,
                is_title_generation=True,
                node_type=node_type_enum,
                http_client=http_client,
                pdf_engine=graph_config.pdf_engine,
            )

            title = ""
            async for chunk in stream_openrouter_response(openRouterReq, pg_engine, redis_manager):
                title += chunk

            await websocket.send_json(
                {
                    "type": "title_response",
                    "node_id": request_data.node_id,
                    "payload": {"title": title.strip()},
                }
            )

    except asyncio.CancelledError:
        logger.info(f"WebSocket stream for node {request_data.node_id} was cancelled.")
        # No need to send a message, as the cancellation was client-initiated
    except Exception as e:
        logger.error(
            f"Error during WebSocket stream for node {request_data.node_id}: {e}", exc_info=True
        )
        await websocket.send_json(
            {
                "type": "stream_error",
                "node_id": request_data.node_id,
                "payload": {"message": str(e)},
            }
        )


async def handle_chat_completion_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
    redis_manager: RedisManager,
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

    messages, file_hashes = await _prepare_and_inject_cached_annotations(
        messages, redis_manager, graph_config.pdf_engine
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
            user_id=user_id,
            pg_engine=pg_engine,
            node_id=request_data.node_id,
            graph_id=request_data.graph_id,
            node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
            http_client=http_client,
            file_hashes=file_hashes,
            pdf_engine=graph_config.pdf_engine,
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
            user_id=user_id,
            pg_engine=pg_engine,
            node_id=request_data.node_id,
            graph_id=request_data.graph_id,
            is_title_generation=True,
            node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
            http_client=http_client,
            pdf_engine=graph_config.pdf_engine,
        )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq, pg_engine, redis_manager),
        media_type="text/plain",
    )


async def handle_parallelization_aggregator_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
    redis_manager: RedisManager,
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

    messages, file_hashes = await _prepare_and_inject_cached_annotations(
        messages, redis_manager, graph_config.pdf_engine
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
        user_id=user_id,
        pg_engine=pg_engine,
        node_id=request_data.node_id,
        graph_id=request_data.graph_id,
        is_title_generation=False,
        node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
        http_client=http_client,
        file_hashes=file_hashes,
        pdf_engine=graph_config.pdf_engine,
    )

    return StreamingResponse(
        stream_openrouter_response(openRouterReq, pg_engine, redis_manager),
        media_type="text/plain",
    )


async def handle_routing_stream(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
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
        user_id=user_id,
        pg_engine=pg_engine,
        node_id=request_data.node_id,
        graph_id=request_data.graph_id,
        is_title_generation=False,
        node_type=NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT,
        schema=schema,
        stream=False,
        http_client=http_client,
        pdf_engine=graph_config.pdf_engine,
    )

    full_response = await make_openrouter_request_non_streaming(openRouterReq, pg_engine)

    return schema.model_validate_json(full_response).model_dump()
