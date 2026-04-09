import asyncio
import json
import logging
import uuid
from asyncio import TimeoutError as AsyncTimeoutError
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.chat_ops import create_tool_call
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.pg.models import ToolCallStatusEnum
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from models.message import NodeTypeEnum, ToolEnum
from models.tool_question import AskUserPendingResult
from pydantic import BaseModel
from services.graph_service import Message
from services.openrouter_schema import build_openrouter_response_format
from services.sandbox_inputs import SandboxInputFileReference
from services.tools import (
    TOOL_HANDLERS_BY_NAME,
    WEB_TOOL_NAMES,
    get_openrouter_tools,
    get_tool_runtime,
    resolve_tool_status,
)
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
ASK_USER_TOOL_NAME = ToolEnum.ASK_USER.value
ASK_USER_BATCH_ERROR = (
    "ask_user must be the only interactive tool call in a tool round. "
    "Ask one question at a time and wait for the user response before requesting more tools."
)


class OpenRouterReq:
    BASE_HEADERS = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://meridian.diikstra.fr/",
        "X-Title": "Meridian",
    }

    def __init__(
        self,
        api_key: str,
        api_url: str = "",
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.headers = {**self.BASE_HEADERS, "Authorization": f"Bearer {api_key}"}
        self.api_url = api_url
        self.http_client = http_client


class OpenRouterReqChat(OpenRouterReq):
    def __init__(
        self,
        api_key: str,
        model: str,
        messages: list[Message] | list[dict[str, Any]],
        config: GraphConfigUpdate,
        user_id: str,
        pg_engine: SQLAlchemyAsyncEngine,
        model_id: Optional[str] = None,
        node_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        is_title_generation: bool = False,
        node_type: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT,
        schema: Optional[type[BaseModel]] = None,
        stream: bool = True,
        http_client: Optional[httpx.AsyncClient] = None,
        file_uuids: Optional[list[str]] = None,
        file_hashes: Optional[dict[str, str]] = None,
        pdf_engine: str = "default",
        selected_tools: Optional[list[ToolEnum]] = None,
        sandbox_input_files: Optional[list[SandboxInputFileReference]] = None,
        sandbox_input_warnings: Optional[list[str]] = None,
    ):
        super().__init__(api_key, OPENROUTER_CHAT_URL)
        self.model = model
        self.model_id = model_id
        self.messages = [
            mess.model_dump(exclude_none=True) if isinstance(mess, Message) else mess
            for mess in messages
        ]
        self.config = config
        self.user_id = user_id
        self.pg_engine = pg_engine
        self.node_id = node_id
        self.graph_id = graph_id
        self.is_title_generation = is_title_generation
        self.node_type = node_type
        self.schema = schema
        self.stream = stream
        self.file_uuids = file_uuids or []
        self.file_hashes = file_hashes or {}
        self.pdf_engine = pdf_engine
        self.selected_tools = selected_tools or []
        self.sandbox_input_files = sandbox_input_files or []
        self.sandbox_input_warnings = sandbox_input_warnings or []

        if http_client is None:
            raise ValueError("http_client must be provided")
        self.http_client = http_client

    def get_payload(self):
        # https://openrouter.ai/docs/api-reference/chat-completion
        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": self.stream,
            "reasoning": {
                "effort": self.config.reasoning_effort,
                "exclude": self.config.exclude_reasoning,
                "enabled": not self.is_title_generation,
            },
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
            "frequency_penalty": self.config.frequency_penalty,
            "presence_penalty": self.config.presence_penalty,
            "repetition_penalty": self.config.repetition_penalty,
            "usage": {
                "include": True,
            },
            "response_format": (
                build_openrouter_response_format(self.schema) if self.schema else None
            ),
        }

        if self.pdf_engine != "default":
            payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": self.pdf_engine}}]

        tools = get_openrouter_tools(self.selected_tools)
        if tools:
            payload["tools"] = tools

        return {k: v for k, v in payload.items() if v is not None}


def _parse_openrouter_error(error_content: bytes) -> str:
    """
    Parses an error response from OpenRouter, with fallbacks for different formats.
    """
    try:
        error_json = json.loads(error_content)
        if "error" in error_json:
            error = error_json["error"]
            if "metadata" in error and "raw" in error["metadata"]:
                try:
                    raw_error = json.loads(error["metadata"]["raw"])
                    if "error" in raw_error and "message" in raw_error["error"]:
                        return str(raw_error["error"]["message"])
                except json.JSONDecodeError:
                    return str(error["metadata"]["raw"])
            return str(error.get("message", "Unknown API error"))
        else:
            return "Unknown API error"
    except json.JSONDecodeError:
        return error_content.decode("utf-8", errors="ignore")


def _process_chunk(
    data_str: str, full_response: str, reasoning_started: bool
) -> tuple[str, str, bool] | None:
    """
    Processes a single data chunk from the SSE stream.

    Returns:
        A tuple (content_to_yield, updated_full_response, updated_reasoning_started) or
            None if chunk is empty/invalid.
    """
    try:
        chunk = json.loads(data_str)
        delta = chunk["choices"][0]["delta"]

        content_to_yield = ""

        # Handle reasoning content
        if "reasoning" in delta and delta["reasoning"]:
            if not reasoning_started:
                content_to_yield += "[THINK]\n"
                reasoning_started = True
            content_to_yield += delta["reasoning"]
            full_response += delta["reasoning"]

        # Handle regular content
        if "content" in delta and delta["content"]:
            # If a reasoning block was active, close it first
            if reasoning_started:
                content_to_yield += "\n[!THINK]\n"
                reasoning_started = False
            content_to_yield += delta["content"]
            full_response += delta["content"]

        if content_to_yield:
            return content_to_yield, full_response, reasoning_started

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"Skipping malformed stream chunk: {data_str} | Error: {e}")

    return None


def _merge_tool_call_chunks(tool_call_chunks):
    """
    Merge streamed tool call chunks into complete tool calls.

    Args:
        tool_call_chunks: List of tool call chunks that may be fragmented

    Returns:
        List of complete tool calls
    """
    if not tool_call_chunks:
        return []

    tool_calls_by_index = {}

    for chunk in tool_call_chunks:
        index = chunk.get("index")
        # A chunk without an index is not usable for grouping.
        if index is None:
            continue

        if index not in tool_calls_by_index:
            # First time seeing this index, initialize the full structure.
            tool_calls_by_index[index] = {
                "id": chunk.get("id"),
                "type": chunk.get("type", "function"),
                "function": {
                    "name": chunk.get("function", {}).get("name", ""),
                    "arguments": chunk.get("function", {}).get("arguments", ""),
                },
            }
        else:
            # This index already exists, so we merge the new chunk's data.
            existing_call = tool_calls_by_index[index]
            func_chunk = chunk.get("function", {})

            # If the ID was missing and this chunk has it, populate it.
            if chunk.get("id") and not existing_call.get("id"):
                existing_call["id"] = chunk.get("id")

            # If the function name was missing, populate it.
            if func_chunk.get("name") and not existing_call["function"]["name"]:
                existing_call["function"]["name"] = func_chunk["name"]

            # Append the arguments chunk.
            if func_chunk.get("arguments"):
                existing_call["function"]["arguments"] += func_chunk.get("arguments")

    # Convert the dictionary back to a list and finalize each tool call.
    result = list(tool_calls_by_index.values())
    for tool_call in result:
        # The API response requires a tool_call_id, so we create a fallback if none was ever
        # provided.
        if not tool_call.get("id"):
            tool_call["id"] = f"call_fallback_{uuid.uuid4().hex}"

        # Clean up and normalize the JSON arguments string.
        args_str = tool_call["function"]["arguments"]
        if args_str:
            args_str = args_str.strip()
            try:
                # Ensure the string is a valid JSON object before parsing.
                if args_str.startswith("{") and args_str.endswith("}"):
                    parsed = json.loads(args_str)
                    # Re-serialize to create a clean, compact JSON string.
                    tool_call["function"]["arguments"] = json.dumps(parsed, separators=(",", ":"))
            except (json.JSONDecodeError, ValueError):
                # If parsing fails (e.g., incomplete JSON), keep the original string.
                pass

    return result


def _normalize_tool_storage_value(tool_value):
    try:
        json.dumps(tool_value)
        return tool_value
    except TypeError:
        return {"value": str(tool_value)}


def _serialize_sandbox_input_files(
    input_files: list[SandboxInputFileReference],
) -> list[dict[str, Any]]:
    return [
        {
            "file_id": input_file.file_id,
            "storage_path": input_file.storage_path,
            "relative_path": input_file.relative_path,
            "name": input_file.name,
            "content_type": input_file.content_type,
            "size": input_file.size,
        }
        for input_file in input_files
    ]


async def _persist_pending_tool_continuation(
    redis_manager: RedisManager,
    *,
    public_tool_call_id: str,
    req: OpenRouterReqChat,
    messages: list[dict[str, Any]],
) -> None:
    await redis_manager.set_pending_tool_continuation(
        public_tool_call_id,
        {
            "messages": messages,
            "model": req.model,
            "model_id": req.model_id,
            "config": req.config.model_dump(mode="json"),
            "user_id": req.user_id,
            "node_id": req.node_id,
            "graph_id": req.graph_id,
            "node_type": req.node_type.value,
            "file_hashes": req.file_hashes,
            "pdf_engine": req.pdf_engine,
            "selected_tools": [tool.value for tool in req.selected_tools],
            "sandbox_input_files": _serialize_sandbox_input_files(req.sandbox_input_files),
            "sandbox_input_warnings": req.sandbox_input_warnings,
        },
    )


def _merge_reasoning_detail_chunks(reasoning_detail_chunks: list[dict]) -> list[dict]:
    """
    Reconstruct streamed reasoning detail fragments into complete reasoning blocks.

    Anthropic/OpenRouter require the last assistant reasoning blocks to be passed back
    unchanged when continuing after tool use. Streaming responses emit these blocks in
    fragments, so we need to reassemble them before replaying them.
    """
    if not reasoning_detail_chunks:
        return []

    merged_by_key: dict[str, dict] = {}
    ordered_keys: list[str] = []

    for chunk in reasoning_detail_chunks:
        chunk_type = chunk.get("type")
        chunk_id = chunk.get("id")
        chunk_index = chunk.get("index")
        chunk_format = chunk.get("format")
        key = f"{chunk_type}:{chunk_id or ''}:{chunk_index if chunk_index is not None else ''}"
        if chunk_format:
            key = f"{key}:{chunk_format}"

        if key not in merged_by_key:
            merged_by_key[key] = {}
            ordered_keys.append(key)

        merged_chunk = merged_by_key[key]

        for field, value in chunk.items():
            if value is None:
                if field not in merged_chunk:
                    merged_chunk[field] = None
                continue

            if field in {"text", "summary", "data"} and isinstance(value, str):
                merged_chunk[field] = f"{merged_chunk.get(field, '')}{value}"
                continue

            if field == "signature":
                merged_chunk[field] = value
                continue

            merged_chunk[field] = value

    return [merged_by_key[key] for key in ordered_keys]


async def _process_tool_calls_and_continue(
    tool_call_chunks,
    messages,
    req,
    redis_manager: RedisManager,
    reasoning_details=None,
    assistant_content=None,
):
    """
    Process tool calls, generate feedback strings, and prepare for the next iteration of
    the conversation loop.
    """
    if not tool_call_chunks:
        return False, messages, req, False, [], False

    # Reconstruct complete tool calls
    complete_tool_calls = _merge_tool_call_chunks(tool_call_chunks)

    # Check if any tool call is a web search
    has_web_search = any(
        tool_call.get("type") == "function"
        and tool_call.get("function", {}).get("name") in WEB_TOOL_NAMES
        for tool_call in complete_tool_calls
    )

    merged_reasoning_details = _merge_reasoning_detail_chunks(reasoning_details or [])

    # Add assistant message with tool calls to the history
    assistant_message = {
        "role": "assistant",
        "content": assistant_content,
        "tool_calls": complete_tool_calls,
    }

    # If we captured reasoning details (containing signatures), pass them back
    if merged_reasoning_details:
        assistant_message["reasoning_details"] = merged_reasoning_details

    messages.append(assistant_message)

    function_tool_calls = [tc for tc in complete_tool_calls if tc.get("type") == "function"]
    feedback_strings = []
    awaiting_user_input = False

    async def persist_tool_call(
        *,
        tool_call: dict[str, Any],
        function_name: str,
        arguments: dict[str, Any],
        normalized_result: dict[str, Any] | list[Any],
        model_context_payload: str,
        status: ToolCallStatusEnum,
    ) -> str:
        public_tool_call_id = str(uuid.uuid4())
        if req.graph_id and req.node_id and req.user_id:
            try:
                persisted_tool_call = await create_tool_call(
                    req.pg_engine,
                    user_id=req.user_id,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    model_id=req.model_id,
                    tool_call_id=tool_call.get("id"),
                    tool_name=function_name,
                    status=status,
                    arguments=_normalize_tool_storage_value(arguments),
                    result=normalized_result,
                    model_context_payload=model_context_payload,
                )
                if persisted_tool_call.id is not None:
                    public_tool_call_id = str(persisted_tool_call.id)
            except Exception:
                logger.warning(
                    "Failed to persist tool call %s for node %s",
                    function_name,
                    req.node_id,
                    exc_info=True,
                )
        return public_tool_call_id

    for index, tool_call in enumerate(function_tool_calls):
        function_name = tool_call["function"]["name"]
        runtime = get_tool_runtime(function_name)
        arguments_str = tool_call["function"]["arguments"]
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            arguments = {}

        if function_name not in TOOL_HANDLERS_BY_NAME:
            tool_result = {"error": f"Unknown tool: {function_name}"}
        else:
            try:
                tool_result = await TOOL_HANDLERS_BY_NAME[function_name](arguments, req)
            except Exception as e:
                tool_result = {"error": f"Tool execution failed: {str(e)}"}

        if function_name == ASK_USER_TOOL_NAME and index != len(function_tool_calls) - 1:
            tool_result = {"error": ASK_USER_BATCH_ERROR}

        normalized_result = _normalize_tool_storage_value(tool_result)
        status = resolve_tool_status(tool_result)
        model_context_payload = json.dumps(normalized_result, separators=(",", ":"))

        if function_name == ASK_USER_TOOL_NAME and status != ToolCallStatusEnum.ERROR:
            pending_result = AskUserPendingResult().model_dump()
            pending_payload = json.dumps(pending_result, separators=(",", ":"))
            public_tool_call_id = await persist_tool_call(
                tool_call=tool_call,
                function_name=function_name,
                arguments=normalized_result if isinstance(normalized_result, dict) else arguments,
                normalized_result=pending_result,
                model_context_payload=pending_payload,
                status=ToolCallStatusEnum.PENDING_USER_INPUT,
            )

            if runtime:
                feedback_strings.append(
                    runtime.summary_renderer(public_tool_call_id, arguments, pending_result)
                )

            await _persist_pending_tool_continuation(
                redis_manager,
                public_tool_call_id=public_tool_call_id,
                req=req,
                messages=messages,
            )
            req.messages = messages
            awaiting_user_input = True
            break

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": model_context_payload,
            }
        )

        public_tool_call_id = await persist_tool_call(
            tool_call=tool_call,
            function_name=function_name,
            arguments=arguments,
            normalized_result=normalized_result,
            model_context_payload=model_context_payload,
            status=status,
        )

        if runtime:
            feedback_strings.append(
                runtime.summary_renderer(public_tool_call_id, arguments, tool_result)
            )

    req.messages = messages

    # Return information about web search and continue flag
    return (
        not awaiting_user_input,
        messages,
        req,
        has_web_search,
        feedback_strings,
        awaiting_user_input,
    )


async def make_openrouter_request_non_streaming(
    req: OpenRouterReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    """
    Makes a non-streaming request to the OpenRouter API and returns the full response content.
    """
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")
    with sentry_sdk.start_span(op="ai.request", description="Non-streaming AI request") as span:
        span.set_tag("chat.model", req.model)
        try:
            response = await client.post(req.api_url, headers=req.headers, json=req.get_payload())
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            if usage_data := data.get("usage"):
                if not req.graph_id or not req.node_id:
                    return str(content)

                await update_node_usage_data(
                    pg_engine=pg_engine,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    usage_data=usage_data,
                    node_type=req.node_type,
                    model_id=req.model_id,
                )

            return str(content)

        except HTTPStatusError as e:
            error_message = _parse_openrouter_error(e.response.content)
            sentry_sdk.set_tag("openrouter.status_code", e.response.status_code)
            logger.error(f"HTTP error from OpenRouter: {e.response.status_code} - {error_message}")
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {e.response.status_code}): {error_message}"
            ) from e
        except (ConnectError, TimeoutException, AsyncTimeoutError) as e:
            logger.error(f"Network/Timeout error connecting to OpenRouter: {e}")
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during non-streaming request: {e}", exc_info=True
            )
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from e


async def stream_openrouter_response(
    req: OpenRouterReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict] = None,
):
    """
    Streams responses from the OpenRouter API asynchronously.

    This function sends a request to the OpenRouter API and yields content
    chunks as they are received in the streaming response. It handles errors
    gracefully and provides appropriate error messages. It also manages
    multi-step tool calls like web search.
    """
    full_response = ""
    clean_content = ""
    reasoning_started = False
    usage_data = {}
    file_annotations = None
    messages = req.messages.copy()
    web_search_active = False
    image_gen_active = False
    collected_reasoning_details = []

    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    try:
        while True:
            async with client.stream(
                "POST", req.api_url, headers=req.headers, json=req.get_payload()
            ) as response:
                if response.status_code != 200:
                    error_content = await response.aread()
                    error_message = _parse_openrouter_error(error_content)
                    sentry_sdk.set_tag("openrouter.status_code", response.status_code)
                    yield f"""[ERROR]Stream Error: Failed to get response from OpenRouter
                                (Status: {response.status_code}). \n{error_message}[!ERROR]"""
                    return

                with sentry_sdk.start_span(
                    op="ai.streaming", description="Stream AI response"
                ) as span:
                    span.set_tag("chat.model", req.model)
                    streamed_bytes = 0
                    chunks_count = 0
                    buffer = ""
                    tool_call_chunks = []
                    finish_reason = None

                    async for byte_chunk in response.aiter_bytes():
                        streamed_bytes += len(byte_chunk)
                        chunks_count += 1

                        buffer += byte_chunk.decode("utf-8", errors="ignore")
                        lines = buffer.splitlines(keepends=True)

                        if lines and not lines[-1].endswith(("\n", "\r")):
                            buffer = lines.pop()
                        else:
                            buffer = ""

                        for line in lines:
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue

                            data_str = line[len("data: ") :].strip()

                            if data_str == "[DONE]":
                                if web_search_active:
                                    yield "[!WEB_SEARCH]\n"
                                    web_search_active = False
                                if image_gen_active:
                                    yield "[!IMAGE_GEN]\n"
                                    image_gen_active = False
                                if reasoning_started:
                                    yield "\n[!THINK]\n"
                                    reasoning_started = False
                                finish_reason = "stop"
                                break

                            try:
                                chunk = json.loads(data_str)
                                if (
                                    "choices" in chunk
                                    and chunk["choices"]
                                    and (
                                        (
                                            "message" in chunk["choices"][0]
                                            and "annotations" in chunk["choices"][0]["message"]
                                        )
                                        or (
                                            "delta" in chunk["choices"][0]
                                            and "annotations" in chunk["choices"][0]["delta"]
                                        )
                                    )
                                ):
                                    file_annotations = chunk["choices"][0].get("message", {}).get(
                                        "annotations"
                                    ) or chunk["choices"][0].get("delta", {}).get("annotations")
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass

                            # Extract usage data
                            if '"usage"' in data_str:
                                try:
                                    usage_chunk = json.loads(data_str)
                                    if new_usage := usage_chunk.get("usage"):
                                        usage_data = new_usage
                                except json.JSONDecodeError:
                                    pass

                            # Process chunk for content or tool calls
                            try:
                                chunk = json.loads(data_str)
                                choice = chunk["choices"][0]
                                delta = choice.get("delta", {})

                                # Collect reasoning details
                                if "reasoning_details" in delta and delta["reasoning_details"]:
                                    collected_reasoning_details.extend(delta["reasoning_details"])

                                if "tool_calls" in delta:
                                    tool_call_chunks.extend(delta["tool_calls"])
                                    for tc in delta["tool_calls"]:
                                        name = tc.get("function", {}).get("name")
                                        if name == "web_search" and not web_search_active:
                                            yield "[WEB_SEARCH]"
                                            web_search_active = True
                                        if (
                                            name
                                            in {
                                                "generate_image",
                                                "generate_image_with_context",
                                                "edit_image",
                                            }
                                            and not image_gen_active
                                        ):
                                            yield "[IMAGE_GEN]"
                                            image_gen_active = True

                                if choice.get("finish_reason") == "tool_calls":
                                    if reasoning_started:
                                        yield "\n[!THINK]\n"
                                        reasoning_started = False
                                    finish_reason = "tool_calls"
                                    break

                                # Track clean content for history
                                if "content" in delta and delta["content"]:
                                    clean_content += delta["content"]

                                processed = _process_chunk(
                                    data_str, full_response, reasoning_started
                                )
                                if processed:
                                    content, full_response, reasoning_started = processed
                                    if web_search_active and content:
                                        yield "[!WEB_SEARCH]\n"
                                        web_search_active = False
                                    if image_gen_active and content:
                                        yield "[!IMAGE_GEN]\n"
                                        image_gen_active = False
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                        if finish_reason:
                            break

                    span.set_data("streamed_bytes", streamed_bytes)
                    span.set_data("chunks_count", chunks_count)

            if finish_reason == "tool_calls":
                (
                    should_continue,
                    messages,
                    req,
                    _,
                    feedback_strings,
                    awaiting_user_input,
                ) = await _process_tool_calls_and_continue(
                    tool_call_chunks,
                    messages,
                    req,
                    redis_manager,
                    reasoning_details=collected_reasoning_details,
                    assistant_content=clean_content if clean_content else None,
                )

                for feedback in feedback_strings:
                    yield feedback

                if should_continue:
                    tool_call_chunks = []
                    full_response = ""
                    clean_content = ""
                    collected_reasoning_details = []
                    continue
                if awaiting_user_input:
                    break
                else:
                    break
            else:
                break

        if file_annotations:
            for annotation in file_annotations:
                if (
                    annotation.get("type") == "file"
                    and (file_info := annotation.get("file"))
                    and (remote_hash := file_info.get("hash"))
                    and (filename := file_info.get("name"))
                ):
                    remote_hash = f"{req.pdf_engine}:{remote_hash}"
                    # Store the annotation using the remote hash
                    await redis_manager.set_annotation(
                        remote_hash=remote_hash,
                        annotation=annotation,
                    )
                    if local_hash := req.file_hashes.get(filename):
                        await redis_manager.set_hash_mapping(
                            local_hash=local_hash,
                            remote_hash=remote_hash,
                        )

        if usage_data and not req.is_title_generation:
            if final_data_container is not None:
                final_data_container["usage_data"] = usage_data

    except asyncio.CancelledError:
        logger.info(f"Stream for node {req.node_id} was cancelled by the connection manager.")
        raise
    except ConnectError as e:
        logger.error(f"Network connection error to OpenRouter: {e}")
        yield """[ERROR]Connection Error: Could not connect to the API.
        Please check your network.[!ERROR]"""
    except (TimeoutException, AsyncTimeoutError) as e:
        logger.error(f"Request to OpenRouter timed out: {e}")
        yield "[ERROR]Timeout: The request to the AI model took too long to respond.[!ERROR]"
    except HTTPStatusError as e:
        logger.error(f"HTTP error from OpenRouter: {e.response.status_code} - {e.response.text}")
        yield f"""[ERROR]HTTP Error: Received an invalid response from the server
        (Status: {e.response.status_code}).[!ERROR]"""
    except Exception as e:
        logger.error(f"An unexpected error occurred during streaming: {e}", exc_info=True)
        yield "[ERROR]An unexpected server error occurred. Please try again later.[!ERROR]"


class Architecture(BaseModel):
    input_modalities: list[str]
    instruct_type: Optional[str] = None
    modality: str
    output_modalities: list[str]
    tokenizer: str


class Pricing(BaseModel):
    completion: str
    image: Optional[str] = None
    internal_reasoning: Optional[str] = None
    prompt: str
    request: Optional[str] = None
    web_search: Optional[str] = None


class TopProvider(BaseModel):
    context_length: Optional[int] = -1
    is_moderated: bool
    max_completion_tokens: Optional[int] = None


class ModelInfo(BaseModel):
    architecture: Architecture
    context_length: Optional[int] = -1
    id: str
    name: str
    icon: Optional[str] = None
    pricing: Pricing
    toolsSupport: bool = False


class ResponseModel(BaseModel):
    data: list[ModelInfo]


BRAND_ICONS = [
    "deepseek",
    "x-ai",
    "cohere",
    "mistralai",
    "meta-llama",
    "google",
    "anthropic",
    "openai",
    "microsoft",
    "qwen",
    "perplexity",
    "nvidia",
    "moonshotai",
    "bytedance",
    "tencent",
    "baidu",
    "ai21",
    "z-ai",
    "nousresearch",
    "openrouter",
    "ibm-granite",
    "liquid",
    "stepfun-ai",
    "minimax",
]


async def list_available_models(req: OpenRouterReq) -> ResponseModel:
    """
    Lists available models from the OpenRouter API.

    This function sends a request to the OpenRouter API to retrieve a list of
    available models. It handles errors gracefully and provides appropriate
    error messages.

    Args:
        req (OpenRouterReq): An object containing the API request details including
                            URL and headers for the OpenRouter API.

    Returns:
        ResponseModel: A Pydantic model containing the list of available models.

    Notes:
        - Uses httpx for asynchronous HTTP communication
        - Handles JSON parsing of the response
        - Logs errors and unexpected responses to the console
    """

    try:
        if req.http_client is not None:
            response = await req.http_client.get(OPENROUTER_MODELS_URL, headers=req.headers)
        else:
            async with httpx.AsyncClient(timeout=60.0, http2=True) as client:
                response = await client.get(OPENROUTER_MODELS_URL, headers=req.headers)

        if response.status_code != 200:
            raise ValueError(
                f"""Failed to get models from AI Provider (Status: {response.status_code}).
                Check backend logs."""
            )

        try:
            raw_models = response.json()
            models = ResponseModel(**raw_models)

            for model, raw_model in zip(models.data, raw_models.get("data", [])):
                brand = model.id.split("/")[0]
                if brand in BRAND_ICONS:
                    model.icon = brand

                model.toolsSupport = raw_model.get("supported_parameters") is not None and (
                    "tools" in raw_model.get("supported_parameters", [])
                )

            return models
        except json.JSONDecodeError:
            logger.warning("Warning: Could not decode JSON response.")
            raise ValueError("Could not decode JSON response.")

    except httpx.RequestError as e:
        logger.error(f"HTTPX Request Error connecting to OpenRouter: {e}")
        raise ValueError(f"Could not connect to AI service. {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during model listing: {e}")
        raise ValueError(f"An unexpected error occurred. {e}")
