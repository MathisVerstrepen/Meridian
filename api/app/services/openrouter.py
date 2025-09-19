import json
import logging
from asyncio import TimeoutError as AsyncTimeoutError
from typing import Optional
import uuid


import httpx
import sentry_sdk
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from fastapi import BackgroundTasks
from httpx import ConnectError, HTTPStatusError, TimeoutException
from models.message import NodeTypeEnum
from pydantic import BaseModel
from services.graph_service import Message
from services.stream_manager import stream_manager
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine
from services.websearch import WEB_SEARCH_TOOL, TOOL_MAPPING

logger = logging.getLogger("uvicorn.error")

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterReq:
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://meridian.diikstra.fr/",
        "X-Title": "Meridian",
    }

    def __init__(self, api_key: str, api_url: str = ""):
        self.headers["Authorization"] = f"Bearer {api_key}"
        self.api_url = api_url


class OpenRouterReqChat(OpenRouterReq):
    def __init__(
        self,
        api_key: str,
        model: str,
        messages: list[Message],
        config: GraphConfigUpdate,
        model_id: Optional[str] = None,
        node_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        is_title_generation: bool = False,
        node_type: NodeTypeEnum = NodeTypeEnum.TEXT_TO_TEXT,
        schema: Optional[type[BaseModel]] = None,
        is_web_search: bool = False,
    ):
        super().__init__(api_key, OPENROUTER_CHAT_URL)
        self.model = model
        self.model_id = model_id
        self.messages = [mess.model_dump(exclude_none=True) for mess in messages]
        self.config = config
        self.node_id = node_id
        self.graph_id = graph_id
        self.is_title_generation = is_title_generation
        self.node_type = node_type
        self.schema = schema
        self.is_web_search = is_web_search

    def get_payload(self):
        # https://openrouter.ai/docs/api-reference/chat-completion
        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": True,
            "reasoning": {
                "effort": self.config.reasoning_effort,
                "exclude": self.config.exclude_reasoning,
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
                {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            **(self.schema.model_json_schema() if self.schema else {}),
                        },
                    },
                }
                if self.schema
                else None
            ),
        }

        if self.is_web_search:
            payload["tools"] = [WEB_SEARCH_TOOL]

        return payload


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
        if "reasoning" in delta and delta["reasoning"] is not None:
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
                "id": chunk.get("id"),  # May be None initially
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
        # The API response requires a tool_call_id, so we create a fallback if none was ever provided.
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


async def _process_tool_calls_and_continue(tool_call_chunks, messages, req):
    """
    Process tool calls and prepare for the next iteration of the conversation loop.

    Args:
        tool_call_chunks: List of tool call chunks to process
        messages: Current conversation messages
        req: OpenRouter request object
        pg_engine: PostgreSQL engine
        background_tasks: FastAPI background tasks

    Returns:
        tuple: (should_continue: bool, updated_messages: list, updated_req: OpenRouterReqChat)
    """
    print("Tool call chunks:", json.dumps(tool_call_chunks, indent=2))

    if not tool_call_chunks:
        return False, messages, req

    # Reconstruct complete tool calls
    complete_tool_calls = _merge_tool_call_chunks(tool_call_chunks)

    # Check if any tool call is a web search
    has_web_search = any(
        tool_call.get("type") == "function"
        and tool_call.get("function", {}).get("name") == "web_search"
        for tool_call in complete_tool_calls
    )

    # Add assistant message with tool calls
    messages.append({"role": "assistant", "content": None, "tool_calls": complete_tool_calls})

    # Execute each tool call
    for tool_call in complete_tool_calls:
        print("Processing tool call:", json.dumps(tool_call, indent=2))
        if tool_call.get("type") == "function":
            function_name = tool_call["function"]["name"]
            try:
                # Parse arguments
                arguments_str = tool_call["function"]["arguments"]
                arguments = json.loads(arguments_str) if arguments_str else {}

                # Execute tool
                if function_name in TOOL_MAPPING:
                    tool_result = await TOOL_MAPPING[function_name](arguments)
                else:
                    tool_result = {"error": f"Unknown tool: {function_name}"}
            except Exception as e:
                tool_result = {"error": f"Tool execution failed: {str(e)}"}

            # Add tool response
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": function_name,
                    "content": json.dumps(tool_result),
                }
            )

    # Update the request with new messages for the next iteration
    req.messages = messages

    # Return information about web search and continue flag
    return True, messages, req, has_web_search


async def stream_openrouter_response(
    req: OpenRouterReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    background_tasks: BackgroundTasks,
):
    """
    Streams responses from the OpenRouter API asynchronously.

    This function sends a request to the OpenRouter API and yields content
    chunks as they are received in the streaming response. It handles errors
    gracefully and provides appropriate error messages.

    Args:
        req (OpenRouterReq): An object containing the API request details including
                            URL, headers, and payload for the OpenRouter API.

    Yields:
        str: Content chunks from the AI model response or error messages.
            Success case: Text fragments from the model's response.
            Error case: Error messages prefixed with "Error:".

    Notes:
        - Uses httpx for asynchronous HTTP communication
        - Handles JSON parsing of streaming data
        - Processes OpenRouter's SSE (Server-Sent Events) format
        - Logs errors and unexpected responses to the console
    """
    stream_manager.set_active(req.graph_id, req.node_id, True)
    full_response = ""
    reasoning_started = False
    usage_data = {}
    messages = req.messages.copy()
    web_search_active = False

    timeout = httpx.Timeout(60.0, connect=10.0, read=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
                        streamed_bytes = 0
                        chunks_count = 0
                        tool_call_chunks = []

                        async for raw_chunk in response.aiter_bytes():
                            streamed_bytes += len(raw_chunk)
                            chunks_count += 1

                            if not stream_manager.is_active(req.graph_id, req.node_id):
                                await response.aclose()
                                logger.info(f"Stream cancelled by client for node {req.node_id}.")
                                span.set_tag("status", "cancelled")
                                return
                            buffer = raw_chunk.decode("utf-8", errors="ignore")
                            lines = buffer.splitlines()

                            # Keep the last line if it's incomplete
                            if lines and not lines[-1].endswith(("\n", "\r")):
                                buffer = lines.pop()
                            else:
                                buffer = ""

                            for line in lines:
                                line = line.strip()
                                if not line.startswith("data: "):
                                    continue

                                data_str = line[6:]  # Remove "data: "

                                if data_str == "[DONE]":
                                    # Close any open tags before ending
                                    if web_search_active:
                                        yield "[!WEB_SEARCH]\n"
                                        web_search_active = False
                                    if reasoning_started:
                                        yield "\n[!THINK]\n"
                                        reasoning_started = False
                                    break

                                # Extract usage data
                                if '"usage"' in data_str:
                                    try:
                                        usage_chunk = json.loads(data_str)
                                        if new_usage := usage_chunk.get("usage"):
                                            usage_data = new_usage
                                    except json.JSONDecodeError:
                                        pass

                                # Process the chunk
                                try:
                                    chunk = json.loads(data_str)
                                    choice = chunk["choices"][0]
                                    delta = choice["delta"]

                                    # Handle tool calls
                                    if "tool_calls" in delta:
                                        tool_call_chunks.extend(delta["tool_calls"])
                                        # Check if this is the start of a web search tool call
                                        for tc in delta["tool_calls"]:
                                            if (
                                                tc.get("function", {}).get("name") == "web_search"
                                                and not web_search_active
                                            ):
                                                yield "[WEB_SEARCH]"
                                                web_search_active = True

                                    # Check for completion
                                    finish_reason = choice.get("finish_reason")
                                    if finish_reason == "tool_calls":
                                        break

                                    # Process regular content
                                    processed = _process_chunk(
                                        data_str, full_response, reasoning_started
                                    )
                                    if processed:
                                        content, full_response, reasoning_started = processed
                                        # Close web search tag if it was active and we're producing content
                                        if web_search_active and content:
                                            yield "[!WEB_SEARCH]\n"
                                            web_search_active = False
                                        yield content

                                except (json.JSONDecodeError, KeyError, IndexError):
                                    continue
                            else:
                                continue
                            break  # Break the async for loop when we're done

                    # Process tool calls if we have any using the extracted function
                    result = await _process_tool_calls_and_continue(tool_call_chunks, messages, req)

                    if result and len(result) >= 4:
                        should_continue, messages, req, has_web_search = result

                        if should_continue:
                            # Reset for next iteration
                            tool_call_chunks = []
                            full_response = ""
                            continue  # Continue to next API call
                        else:
                            break
                    else:
                        span.set_data("streamed_bytes", streamed_bytes)
                        span.set_data("chunks_count", chunks_count)
                        break

            # Close any remaining open tags
            if web_search_active:
                yield "[!WEB_SEARCH]\n"
            if reasoning_started:
                yield "\n[!THINK]\n"

            if usage_data and not req.is_title_generation:
                if not req.graph_id or not req.node_id:
                    return
                background_tasks.add_task(
                    update_node_usage_data,
                    pg_engine=pg_engine,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    usage_data=usage_data,
                    node_type=req.node_type,
                    model_id=req.model_id,
                )

    except ConnectError as e:
        logger.error(f"Network connection error to OpenRouter: {e}")
        yield """[ERROR]Connection Error: Could not connect to the API. 
        Please check your network.[!ERROR]"""
    except (TimeoutException, AsyncTimeoutError) as e:
        logger.error(f"Request to OpenRouter timed out: {e}")
        yield "[ERROR]Timeout: The request to the AI model took too long to respond.[!ERROR]"
    except HTTPStatusError as e:
        logger.error(f"HTTP error from OpenRouter: {e.response.status_code} - {e.response.text}")
        yield """[ERROR]HTTP Error: Received an invalid response from the server 
        (Status: {e.response.status_code}).[!ERROR]"""
    except Exception as e:
        logger.error(f"An unexpected error occurred during streaming: {e}", exc_info=True)
        yield "[ERROR]An unexpected server error occurred. Please try again later.[!ERROR]"

    finally:
        if web_search_active:
            yield "[!WEB_SEARCH]\n"
        stream_manager.set_active(req.graph_id, req.node_id, False)


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
    created: int
    description: str
    id: str
    name: str
    icon: Optional[str] = None
    per_request_limits: Optional[str] = None
    pricing: Pricing
    supported_parameters: list[str]
    top_provider: TopProvider


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
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(OPENROUTER_MODELS_URL, headers=req.headers)
            if response.status_code != 200:
                raise ValueError(
                    f"""Failed to get models from AI Provider (Status: {response.status_code}).
                    Check backend logs."""
                )

            try:
                data = response.json()
                models = ResponseModel(**data)

                for model in models.data:
                    brand = model.id.split("/")[0]
                    if brand in BRAND_ICONS:
                        model.icon = brand

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
