import asyncio
import json
import logging
from asyncio import TimeoutError as AsyncTimeoutError
from typing import Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_config_crud import GraphConfigUpdate
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from models.message import NodeTypeEnum
from pydantic import BaseModel
from services.graph_service import Message
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

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
        stream: bool = True,
        http_client: Optional[httpx.AsyncClient] = None,
        file_uuids: Optional[list[str]] = None,
        file_hashes: Optional[dict[str, str]] = None,
        pdf_engine: str = "default",
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
        self.stream = stream
        self.file_uuids = file_uuids or []
        self.file_hashes = file_hashes or {}
        self.pdf_engine = pdf_engine

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

        if self.pdf_engine != "default":
            payload["plugins"] = [{"id": "file-parser", "pdf": {"engine": self.pdf_engine}}]

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


async def make_openrouter_request_non_streaming(
    req: OpenRouterReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    """
    Makes a non-streaming request to the OpenRouter API and returns the full response content.
    """
    client = req.http_client
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
        raise ValueError(f"API Error (Status: {e.response.status_code}): {error_message}") from e
    except (ConnectError, TimeoutException, AsyncTimeoutError) as e:
        logger.error(f"Network/Timeout error connecting to OpenRouter: {e}")
        raise ConnectionError(
            "Could not connect to the AI service. Please check your network."
        ) from e
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during non-streaming request: {e}", exc_info=True
        )
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
    full_response = ""
    reasoning_started = False
    usage_data = {}
    file_annotations = None

    client = req.http_client

    try:
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

            with sentry_sdk.start_span(op="ai.streaming", description="Stream AI response") as span:
                streamed_bytes = 0
                chunks_count = 0
                # Buffer for incomplete SSE messages
                buffer = ""
                async for byte_chunk in response.aiter_bytes():
                    streamed_bytes += len(byte_chunk)
                    chunks_count += 1

                    buffer += byte_chunk.decode("utf-8", errors="ignore")
                    lines = buffer.splitlines(keepends=True)

                    # Keep the last line if it's incomplete
                    if lines and not lines[-1].endswith(("\n", "\r")):
                        buffer = lines.pop()
                    else:
                        buffer = ""

                    for line in lines:
                        line = line.strip()
                        if line.startswith("data: "):
                            data_str = line[len("data: ") :].strip()

                            if data_str == "[DONE]":
                                if reasoning_started:
                                    yield "\n[!THINK]\n"
                                break

                            # Capture annotations from non-delta message chunks
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

                            processed = _process_chunk(data_str, full_response, reasoning_started)
                            if processed:
                                content, full_response, reasoning_started = processed
                                yield content
                    else:
                        continue
                    break
                span.set_data("streamed_bytes", streamed_bytes)
                span.set_data("chunks_count", chunks_count)

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

                    # Store the local -> remote hash mapping
                    if local_hash := req.file_hashes.get(filename):
                        await redis_manager.set_hash_mapping(
                            local_hash=local_hash,
                            remote_hash=remote_hash,
                        )

        if usage_data and not req.is_title_generation:
            if final_data_container is not None:
                final_data_container["usage_data"] = usage_data

    # Specific exception handling
    except asyncio.CancelledError:
        logger.info(f"Stream for node {req.node_id} was cancelled by the connection manager.")
        # Re-raise to ensure the parent task knows about the cancellation
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
        yield """[ERROR]HTTP Error: Received an invalid response from the server 
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
