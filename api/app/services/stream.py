import asyncio
import logging
from typing import Any

import httpx
from const.prompts import (
    AUTO_TOOL_SELECTION_SYSTEM_PROMPT,
    TITLE_GENERATION_PROMPT,
    TOOL_CODE_EXECUTION_GUIDE,
    TOOL_FETCH_PAGE_CONTENT_GUIDE,
    TOOL_IMAGE_GENERATION_GUIDE,
    TOOL_USAGE_GUIDE_HEADER,
    TOOL_VISUALISE_GUIDE,
    TOOL_WEB_SEARCH_GUIDE,
)
from database.neo4j.crud import (
    get_all_nodes_of_type_in_graph,
    get_connected_prompt_nodes,
    get_root_nodes_of_type,
)
from database.pg.graph_ops.graph_node_crud import get_nodes_by_ids
from database.pg.models import Node
from database.redis.redis_ops import RedisManager
from fastapi import WebSocket
from fastapi.responses import StreamingResponse
from models.chatDTO import GenerateRequest
from models.message import (
    Message,
    MessageContent,
    MessageContentTypeEnum,
    MessageRoleEnum,
    NodeTypeEnum,
    ToolEnum,
)
from neo4j import AsyncDriver
from pydantic import BaseModel
from services.graph_service import (
    construct_message_history,
    construct_parallelization_aggregator_prompt,
    construct_routing_prompt,
    get_effective_graph_config,
)
from services.node import (
    CleanTextOption,
    extract_context_prompt,
    get_first_user_prompt,
    system_message_builder,
)
from services.openrouter import (
    OpenRouterReqChat,
    make_openrouter_request_non_streaming,
    stream_openrouter_response,
)
from services.settings import get_user_settings
from services.sandbox_inputs import (
    SandboxInputFileReference,
    build_sandbox_input_manifest,
    collect_sandbox_input_files,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

ROUTING_MODEL = "deepseek/deepseek-v3.2"
TITLE_GENERATION_MODEL = "x-ai/grok-4.1-fast"
AUTO_TOOL_SELECTION_MODEL = "x-ai/grok-4.1-fast"
AUTO_TOOL_CANDIDATES_BY_NODE_TYPE: dict[NodeTypeEnum, list[ToolEnum]] = {
    NodeTypeEnum.TEXT_TO_TEXT: [
        ToolEnum.WEB_SEARCH,
        ToolEnum.LINK_EXTRACTION,
        ToolEnum.IMAGE_GENERATION,
        ToolEnum.EXECUTE_CODE,
        ToolEnum.VISUALISE,
    ],
    NodeTypeEnum.ROUTING: [
        ToolEnum.WEB_SEARCH,
        ToolEnum.LINK_EXTRACTION,
        ToolEnum.IMAGE_GENERATION,
        ToolEnum.EXECUTE_CODE,
        ToolEnum.VISUALISE,
    ],
}
TOOL_DEPENDENCIES: dict[ToolEnum, list[ToolEnum]] = {
    ToolEnum.WEB_SEARCH: [ToolEnum.LINK_EXTRACTION],
}
AUTO_TOOL_DESCRIPTIONS: dict[ToolEnum, str] = {
    ToolEnum.WEB_SEARCH: "Search the web for recent or external information.",
    ToolEnum.LINK_EXTRACTION: "Read and extract content from specific web pages or URLs.",
    ToolEnum.IMAGE_GENERATION: "Generate images from a prompt.",
    ToolEnum.EXECUTE_CODE: "Run Python code for exact calculations, debugging, or analysis.",
    ToolEnum.VISUALISE: "Create Mermaid, SVG, or HTML visuals, charts, and explainers.",
}


class AutoToolSelectionSchema(BaseModel):
    selected_tools: list[ToolEnum] = []


def _append_visualise_node_constraints(system_prompt: str, node: list[Node] | None) -> str:
    if not node or not isinstance(node[0].data, dict):
        return system_prompt

    visualise_modes = node[0].data.get("visualiseModes")
    if not isinstance(visualise_modes, dict):
        return system_prompt

    disabled_modes: list[str] = []
    if visualise_modes.get("enableMermaid") is False:
        disabled_modes.append("mermaid")
    if visualise_modes.get("enableSvg") is False:
        disabled_modes.append("svg")
    if visualise_modes.get("enableHtml") is False:
        disabled_modes.append("html")

    if not disabled_modes:
        return system_prompt

    disabled_list = ", ".join(disabled_modes)
    return (
        system_prompt
        + "\n"
        + "Visualise node constraint: for this node, these output modes are disabled: "
        + disabled_list
        + ". Do not request those output modes from the visualise tool."
    )


def _normalize_selected_tools(selected_tools: list[Any] | None) -> list[ToolEnum]:
    normalized: list[ToolEnum] = []
    for tool in selected_tools or []:
        try:
            normalized_tool = ToolEnum(str(tool))
        except ValueError:
            continue
        if normalized_tool not in normalized:
            normalized.append(normalized_tool)
    return normalized


def _expand_tool_dependencies(selected_tools: list[ToolEnum]) -> list[ToolEnum]:
    expanded = list(selected_tools)
    for tool in list(selected_tools):
        for dependency in TOOL_DEPENDENCIES.get(tool, []):
            if dependency not in expanded:
                expanded.append(dependency)
    return expanded


def _append_tool_guides(
    system_prompt: str,
    selected_tools: list[ToolEnum],
    node: list[Node] | None,
) -> str:
    if len(selected_tools) == 0:
        return system_prompt

    system_prompt = (
        system_prompt
        + "\n"
        + TOOL_USAGE_GUIDE_HEADER.format(tool_list=", ".join([tool for tool in selected_tools]))
    )

    if ToolEnum.WEB_SEARCH in selected_tools:
        system_prompt = system_prompt + "\n" + TOOL_WEB_SEARCH_GUIDE

    if ToolEnum.LINK_EXTRACTION in selected_tools:
        system_prompt = system_prompt + "\n" + TOOL_FETCH_PAGE_CONTENT_GUIDE

    if ToolEnum.IMAGE_GENERATION in selected_tools:
        system_prompt = system_prompt + "\n" + TOOL_IMAGE_GENERATION_GUIDE

    if ToolEnum.EXECUTE_CODE in selected_tools:
        system_prompt = system_prompt + "\n" + TOOL_CODE_EXECUTION_GUIDE

    if ToolEnum.VISUALISE in selected_tools:
        system_prompt = system_prompt + "\n" + TOOL_VISUALISE_GUIDE
        system_prompt = _append_visualise_node_constraints(system_prompt, node)

    return system_prompt


def _is_visualise_available(node: list[Node] | None, settings) -> bool:
    if not settings.toolsVisualise.enableMermaid and not settings.toolsVisualise.enableSvg:
        if not settings.toolsVisualise.enableHtml:
            return False

    node_data = node[0].data if node and isinstance(node[0].data, dict) else {}
    visualise_modes = (
        node_data.get("visualiseModes", {})
        if isinstance(node_data, dict) and isinstance(node_data.get("visualiseModes", {}), dict)
        else {}
    )

    return any(
        [
            bool(settings.toolsVisualise.enableMermaid)
            and visualise_modes.get("enableMermaid", True),
            bool(settings.toolsVisualise.enableSvg) and visualise_modes.get("enableSvg", True),
            bool(settings.toolsVisualise.enableHtml) and visualise_modes.get("enableHtml", True),
        ]
    )


async def _get_auto_selector_prompt_text(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
) -> str:
    connected_nodes_records = await get_connected_prompt_nodes(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        generator_node_id=node_id,
    )
    if not connected_nodes_records:
        return ""

    prompt_node_ids = [
        node.id for node in connected_nodes_records if node.type == NodeTypeEnum.PROMPT
    ]
    if not prompt_node_ids:
        return ""

    nodes_data = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=prompt_node_ids,
    )

    return extract_context_prompt(connected_nodes_records, nodes_data).strip()


def _get_auto_tool_candidates(
    node_type: NodeTypeEnum,
    node: list[Node] | None,
    settings,
) -> list[ToolEnum]:
    candidates = list(AUTO_TOOL_CANDIDATES_BY_NODE_TYPE.get(node_type, []))
    if ToolEnum.VISUALISE in candidates and not _is_visualise_available(node, settings):
        candidates.remove(ToolEnum.VISUALISE)
    return candidates


async def _resolve_auto_selected_tools(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
    graph_config,
    open_router_api_key: str,
    node: list[Node] | None,
    node_type_enum: NodeTypeEnum,
) -> list[ToolEnum]:
    settings = await get_user_settings(pg_engine, user_id)
    candidates = _get_auto_tool_candidates(node_type_enum, node, settings)
    if not candidates:
        return []

    prompt_text = await _get_auto_selector_prompt_text(
        pg_engine=pg_engine,
        neo4j_driver=neo4j_driver,
        graph_id=request_data.graph_id,
        node_id=request_data.node_id,
    )
    if not prompt_text:
        return []

    selector_config = graph_config.model_copy(deep=True)
    selector_config.temperature = 0.5
    selector_config.exclude_reasoning = True

    tool_lines = "\n".join(f"- {tool.value}: {AUTO_TOOL_DESCRIPTIONS[tool]}" for tool in candidates)
    selector_messages = [
        Message(
            role=MessageRoleEnum.system,
            content=[
                MessageContent(
                    type=MessageContentTypeEnum.text,
                    text=AUTO_TOOL_SELECTION_SYSTEM_PROMPT,
                )
            ],
        ),
        Message(
            role=MessageRoleEnum.user,
            content=[
                MessageContent(
                    type=MessageContentTypeEnum.text,
                    text=(
                        "Latest prompt:\n" f"{prompt_text}\n\n" "Available tools:\n" f"{tool_lines}"
                    ),
                )
            ],
        ),
    ]

    selector_request = OpenRouterReqChat(
        api_key=open_router_api_key,
        model=AUTO_TOOL_SELECTION_MODEL,
        messages=selector_messages,
        config=selector_config,
        user_id=user_id,
        pg_engine=pg_engine,
        node_id=request_data.node_id,
        graph_id=request_data.graph_id,
        node_type=node_type_enum,
        schema=AutoToolSelectionSchema,
        stream=False,
        http_client=http_client,
        pdf_engine=graph_config.pdf_engine,
    )

    try:
        selector_response = await make_openrouter_request_non_streaming(selector_request, pg_engine)
        parsed_response = AutoToolSelectionSchema.model_validate_json(selector_response)
    except Exception:
        logger.warning(
            "Auto tool selection failed for node %s",
            request_data.node_id,
            exc_info=True,
        )
        return []

    selected_tools = [tool for tool in parsed_response.selected_tools if tool in candidates]
    return _expand_tool_dependencies(selected_tools)


async def _resolve_selected_tools(
    system_prompt: str,
    node: list[Node] | None,
    node_type_enum: NodeTypeEnum,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    request_data: GenerateRequest,
    user_id: str,
    http_client: httpx.AsyncClient,
    graph_config,
    open_router_api_key: str,
) -> tuple[list[ToolEnum], str]:
    node_data = node[0].data if node and isinstance(node[0].data, dict) else {}
    auto_select_tools = (
        bool(node_data.get("autoSelectTools")) if isinstance(node_data, dict) else False
    )

    if auto_select_tools:
        selected_tools = await _resolve_auto_selected_tools(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            request_data=request_data,
            user_id=user_id,
            http_client=http_client,
            graph_config=graph_config,
            open_router_api_key=open_router_api_key,
            node=node,
            node_type_enum=node_type_enum,
        )
    else:
        selected_tools = _normalize_selected_tools(
            node_data.get("selectedTools", []) if isinstance(node_data, dict) else []
        )
        selected_tools = _expand_tool_dependencies(selected_tools)

    return selected_tools, _append_tool_guides(system_prompt, selected_tools, node)


async def _prepare_execute_code_inputs(
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    node_id: str,
    user_id: str,
) -> tuple[list[SandboxInputFileReference], list[str]]:
    connected_nodes_records = await get_connected_prompt_nodes(
        neo4j_driver=neo4j_driver,
        graph_id=graph_id,
        generator_node_id=node_id,
    )
    if not connected_nodes_records:
        return [], []

    connected_nodes_data = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=graph_id,
        node_ids=[node.id for node in connected_nodes_records],
    )

    return await collect_sandbox_input_files(
        user_id=user_id,
        connected_nodes=connected_nodes_records,
        connected_nodes_data=connected_nodes_data,
        pg_engine=pg_engine,
    )


def _append_execute_code_manifest(
    messages: list[Message],
    sandbox_input_files: list[SandboxInputFileReference],
    sandbox_input_warnings: list[str],
) -> list[Message]:
    if not sandbox_input_files and not sandbox_input_warnings:
        return messages

    target_message = next(
        (message for message in reversed(messages) if message.role == MessageRoleEnum.user),
        None,
    )
    if target_message is None:
        return messages

    target_message.content.append(
        MessageContent(
            type=MessageContentTypeEnum.text,
            text=build_sandbox_input_manifest(sandbox_input_files, sandbox_input_warnings),
        )
    )
    return messages


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

        sandbox_input_files: list[SandboxInputFileReference] = []
        sandbox_input_warnings: list[str] = []

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
                model=ROUTING_MODEL,
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
        selectedTools: list[ToolEnum] = []
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
            or request_data.stream_type == NodeTypeEnum.CONTEXT_MERGER
        ):
            if not is_title_generation:
                selectedTools, system_prompt = await _resolve_selected_tools(
                    system_prompt=system_prompt,
                    node=node,
                    node_type_enum=node_type_enum,
                    pg_engine=pg_engine,
                    neo4j_driver=neo4j_driver,
                    request_data=request_data,
                    user_id=user_id,
                    http_client=http_client,
                    graph_config=graph_config,
                    open_router_api_key=open_router_api_key,
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

            # Special handling for ContextMerger to send branch summaries if available
            # if any message is a ContextMerger node
            for message in messages:
                if message.metadata and message.node_id:
                    await websocket.send_json(
                        {
                            "type": "node_data_update",
                            "node_id": message.node_id,
                            "graph_id": request_data.graph_id,
                            "payload": message.metadata,
                        }
                    )
                    message.metadata = None

            openRouterReq = None
        else:
            raise ValueError(f"Unsupported stream type: {request_data.stream_type}")

        if ToolEnum.EXECUTE_CODE in selectedTools:
            sandbox_input_files, sandbox_input_warnings = await _prepare_execute_code_inputs(
                pg_engine=pg_engine,
                neo4j_driver=neo4j_driver,
                graph_id=request_data.graph_id,
                node_id=request_data.node_id,
                user_id=user_id,
            )
            messages = _append_execute_code_manifest(
                messages,
                sandbox_input_files,
                sandbox_input_warnings,
            )

        messages, file_hashes = await _prepare_and_inject_cached_annotations(
            messages, redis_manager, graph_config.pdf_engine
        )

        if not is_title_generation:
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
                node_type=node_type_enum,
                http_client=http_client,
                file_hashes=file_hashes,
                pdf_engine=graph_config.pdf_engine,
                selected_tools=selectedTools,
                sandbox_input_files=sandbox_input_files,
                sandbox_input_warnings=sandbox_input_warnings,
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
                model=TITLE_GENERATION_MODEL,
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

    node = await get_nodes_by_ids(
        pg_engine=pg_engine,
        graph_id=request_data.graph_id,
        node_ids=[request_data.node_id],
    )
    node_type_enum = NodeTypeEnum(node[0].type) if node else NodeTypeEnum.TEXT_TO_TEXT
    selectedTools: list[ToolEnum] = []
    if not request_data.title:
        selectedTools, system_prompt = await _resolve_selected_tools(
            system_prompt=system_prompt,
            node=node,
            node_type_enum=node_type_enum,
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            request_data=request_data,
            user_id=user_id,
            http_client=http_client,
            graph_config=graph_config,
            open_router_api_key=open_router_api_key,
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

    sandbox_input_files: list[SandboxInputFileReference] = []
    sandbox_input_warnings: list[str] = []
    if ToolEnum.EXECUTE_CODE in selectedTools:
        sandbox_input_files, sandbox_input_warnings = await _prepare_execute_code_inputs(
            pg_engine=pg_engine,
            neo4j_driver=neo4j_driver,
            graph_id=request_data.graph_id,
            node_id=request_data.node_id,
            user_id=user_id,
        )
        messages = _append_execute_code_manifest(
            messages,
            sandbox_input_files,
            sandbox_input_warnings,
        )

    messages, file_hashes = await _prepare_and_inject_cached_annotations(
        messages, redis_manager, graph_config.pdf_engine
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
            node_type=node_type_enum,
            http_client=http_client,
            file_hashes=file_hashes,
            pdf_engine=graph_config.pdf_engine,
            selected_tools=selectedTools,
            sandbox_input_files=sandbox_input_files,
            sandbox_input_warnings=sandbox_input_warnings,
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
            model=TITLE_GENERATION_MODEL,
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
        model=ROUTING_MODEL,
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


async def regenerate_title_stream(
    websocket: WebSocket,
    pg_engine: SQLAlchemyAsyncEngine,
    neo4j_driver: AsyncDriver,
    graph_id: str,
    strategy: str,
    user_id: str,
    http_client: httpx.AsyncClient,
    redis_manager: RedisManager,
):
    """
    Regenerates the graph title based on the specified strategy ('first' or 'all').
    Uses graph topology (root node detection) to identify the 'first' node in the absence
    of timestamp data on nodes.
    """
    try:
        graph_config, _, open_router_api_key = await get_effective_graph_config(
            pg_engine=pg_engine,
            graph_id=graph_id,
            user_id=user_id,
        )

        prompt_text = ""

        if strategy == "all":
            prompt_node_ids = await get_all_nodes_of_type_in_graph(
                neo4j_driver=neo4j_driver, graph_id=graph_id, node_types=[NodeTypeEnum.PROMPT]
            )

            if prompt_node_ids:
                nodes = await get_nodes_by_ids(
                    pg_engine=pg_engine,
                    graph_id=graph_id,
                    node_ids=prompt_node_ids,
                )

                # Concatenate content from all prompts
                combined_content = []
                for node in nodes:
                    if isinstance(node.data, dict) and (content := node.data.get("prompt")):
                        # Truncate if too long
                        if len(content) > 1000:
                            content = f"{content[:500]}...{content[-500:]}"

                        combined_content.append(str(content))

                prompt_text = "\n---\n".join(combined_content)

        else:  # 'first' or default
            root_ids = await get_root_nodes_of_type(
                neo4j_driver=neo4j_driver, graph_id=graph_id, node_types=[NodeTypeEnum.PROMPT]
            )

            node_id_to_fetch = None
            if root_ids:
                node_id_to_fetch = root_ids[0]
            else:
                all_ids = await get_all_nodes_of_type_in_graph(
                    neo4j_driver=neo4j_driver, graph_id=graph_id, node_types=[NodeTypeEnum.PROMPT]
                )
                if all_ids:
                    node_id_to_fetch = all_ids[0]

            if node_id_to_fetch:
                nodes = await get_nodes_by_ids(
                    pg_engine=pg_engine,
                    graph_id=graph_id,
                    node_ids=[node_id_to_fetch],
                )
                if nodes and isinstance(nodes[0].data, dict):
                    prompt_text = str(nodes[0].data.get("prompt", ""))

            # Truncate if too long
            if len(prompt_text) > 2000:
                prompt_text = f"{prompt_text[:1000]}...{prompt_text[-1000:]}"

        if not prompt_text:
            prompt_text = "New Canvas"

        # Construct message for LLM
        user_msg = Message(
            role=MessageRoleEnum.user,
            content=[MessageContent(type=MessageContentTypeEnum.text, text=prompt_text)],
        )

        graph_config.max_tokens = 50
        system_msg = system_message_builder(TITLE_GENERATION_PROMPT)
        messages = [system_msg] if system_msg is not None else []
        messages.append(user_msg)

        openRouterReq = OpenRouterReqChat(
            api_key=open_router_api_key,
            model=TITLE_GENERATION_MODEL,
            messages=messages,
            config=graph_config,
            user_id=user_id,
            pg_engine=pg_engine,
            node_id=None,
            graph_id=graph_id,
            is_title_generation=True,
            node_type=NodeTypeEnum.TEXT_TO_TEXT,
            http_client=http_client,
            pdf_engine=graph_config.pdf_engine,
        )

        title = ""
        async for chunk in stream_openrouter_response(openRouterReq, pg_engine, redis_manager):
            title += chunk

        await websocket.send_json(
            {
                "type": "title_response",
                "node_id": graph_id,
                "payload": {"title": title.strip()},
            }
        )

    except Exception as e:
        logger.error(f"Error generating title for graph {graph_id}: {e}", exc_info=True)
        await websocket.send_json(
            {
                "type": "stream_error",
                "node_id": graph_id,
                "payload": {"message": str(e)},
            }
        )
