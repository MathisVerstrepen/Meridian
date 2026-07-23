import json
import logging
import re
from asyncio import TimeoutError as AsyncTimeoutError
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from services.providers.alibaba_token_plan_catalog import ALIBABA_TOKEN_PLAN_MODEL_PREFIX
from services.providers.common import (
    BaseProviderReq,
    has_file_attachments,
    normalize_max_tokens,
    normalize_temperature,
    normalize_top_p,
    strip_model_prefix,
    validate_http_client_for_tools,
    validate_supported_tools,
)
from services.tools import get_openrouter_tools
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

ALIBABA_TOKEN_PLAN_BASE_URL = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
ALIBABA_TOKEN_PLAN_CHAT_URL = f"{ALIBABA_TOKEN_PLAN_BASE_URL}/chat/completions"
ALIBABA_TOKEN_PLAN_VALIDATION_MODEL = "qwen3.6-flash"
ALIBABA_TOKEN_PLAN_NON_STREAMING_TIMEOUT = httpx.Timeout(
    300.0,
    connect=10.0,
    read=300.0,
)
ALIBABA_TOKEN_PLAN_FALLBACK_USER_CONTENT = "Please respond to the available context."
ALIBABA_ERROR_MESSAGE_LIMIT = 500


def _parse_alibaba_error(error_content: bytes) -> str:
    message = "Alibaba returned an unknown API error."
    try:
        payload = json.loads(error_content)
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict) and error.get("message"):
            message = str(error["message"])
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        pass

    sanitized = " ".join(message.split())
    sanitized = re.sub(r"sk-sp-[A-Za-z0-9._~+/=-]+", "[REDACTED]", sanitized)
    return sanitized[:ALIBABA_ERROR_MESSAGE_LIMIT]


def _validate_api_key_prefix(api_key: str) -> str:
    normalized = api_key.strip()
    if not normalized:
        raise ValueError("API key is required.")
    if not normalized.startswith("sk-sp-"):
        raise ValueError("Alibaba Personal Token Plan API keys must start with 'sk-sp-'.")
    return normalized


def _model_id(model: str) -> str:
    if not model.startswith(ALIBABA_TOKEN_PLAN_MODEL_PREFIX):
        raise ValueError("Invalid Alibaba Token Plan model prefix.")
    model_id = strip_model_prefix(model, ALIBABA_TOKEN_PLAN_MODEL_PREFIX).strip()
    if not model_id:
        raise ValueError("Alibaba Token Plan model ID is required.")
    return model_id


class AlibabaTokenPlanReq:
    BASE_HEADERS = {"Content-Type": "application/json"}

    def __init__(self, api_key: str, http_client: httpx.AsyncClient | None = None) -> None:
        self.api_key = _validate_api_key_prefix(api_key)
        self.alibaba_token_plan_api_key = self.api_key
        self.headers = {
            **self.BASE_HEADERS,
            "Authorization": f"Bearer {self.api_key}",
        }
        self.api_url = ALIBABA_TOKEN_PLAN_CHAT_URL
        self.http_client = http_client


@dataclass(kw_only=True)
class AlibabaTokenPlanReqChat(BaseProviderReq, AlibabaTokenPlanReq):
    api_key: str
    http_client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        AlibabaTokenPlanReq.__init__(
            self,
            api_key=self.api_key,
            http_client=self.http_client,
        )
        if self.http_client is None:
            raise ValueError("http_client must be provided")

    def validate_request(self) -> None:
        _model_id(self.model)
        if self.schema is not None:
            raise ValueError(
                "Alibaba Personal Token Plan models do not support structured-output helpers."
            )

        validate_supported_tools("Alibaba Personal Token Plan", self.selected_tools)

        if (
            self.file_uuids
            or self.file_hashes
            or self.sandbox_input_files
            or has_file_attachments(self.messages)
        ):
            raise ValueError(
                "Alibaba Personal Token Plan models do not support file or PDF attachments."
            )

        if not self.stream and self.selected_tools:
            raise ValueError("Alibaba Personal Token Plan tool execution requires streaming mode.")

        validate_http_client_for_tools(
            "Alibaba Personal Token Plan",
            self.selected_tools,
            self.http_client,
        )

    def get_payload(self) -> dict[str, Any]:
        from services.providers.openai_protocol import (
            normalize_openai_request_message,
            sanitize_openai_messages,
        )

        normalized_messages = [
            normalize_openai_request_message(
                message,
                include_reasoning_content=True,
                preserve_content_parts=True,
                strip_text=False,
            )
            for message in self.messages
            if isinstance(message, dict)
        ]
        messages = sanitize_openai_messages(
            normalized_messages,
            fallback_user_content=ALIBABA_TOKEN_PLAN_FALLBACK_USER_CONTENT,
            provider_label="Alibaba Personal Token Plan",
            preserve_content_parts=True,
        )
        payload: dict[str, Any] = {
            "model": _model_id(self.model),
            "messages": messages,
            "stream": self.stream,
            "temperature": normalize_temperature(getattr(self.config, "temperature", None)),
            "top_p": normalize_top_p(getattr(self.config, "top_p", None)),
            "max_tokens": normalize_max_tokens(getattr(self.config, "max_tokens", None)),
            "enable_thinking": not (
                self.is_title_generation or bool(getattr(self.config, "exclude_reasoning", False))
            ),
        }
        if self.stream:
            payload["stream_options"] = {"include_usage": True}

        tools = get_openrouter_tools(self.selected_tools)
        if tools:
            payload["tools"] = tools
            if _model_id(self.model).casefold().startswith("glm-") and self.stream:
                payload["tool_stream"] = True

        return {key: value for key, value in payload.items() if value is not None}


def _message_metadata(req: AlibabaTokenPlanReqChat) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for message in req.messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            content_length = sum(
                len(str(part.get("text") or ""))
                for part in content
                if isinstance(part, dict) and str(part.get("type") or "") == "text"
            )
            has_image = any(
                isinstance(part, dict) and str(part.get("type") or "") == "image_url"
                for part in content
            )
        else:
            content_length = len(str(content or ""))
            has_image = False
        metadata.append(
            {
                "role": str(message.get("role") or ""),
                "content_length": content_length,
                "has_image": has_image,
                "has_tool_calls": bool(message.get("tool_calls")),
            }
        )
    return metadata


def _log_alibaba_rejected_request(req: AlibabaTokenPlanReqChat) -> None:
    logger.error(
        "Alibaba Personal Token Plan rejected request model=%s messages=%s",
        _model_id(req.model),
        _message_metadata(req),
    )


async def validate_alibaba_token_plan_api_key(
    api_key: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    normalized_api_key = _validate_api_key_prefix(api_key)
    payload = {
        "model": ALIBABA_TOKEN_PLAN_VALIDATION_MODEL,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "max_tokens": 16,
        "enable_thinking": False,
    }

    async def _do_validate(client: httpx.AsyncClient) -> None:
        response = await client.post(
            ALIBABA_TOKEN_PLAN_CHAT_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {normalized_api_key}",
            },
            json=payload,
        )
        if response.status_code != 200:
            raise ValueError(
                "Alibaba Personal Token Plan validation failed "
                f"(status {response.status_code}): {_parse_alibaba_error(response.content)}"
            )
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(
                "Alibaba Personal Token Plan validation returned an invalid response."
            ) from exc

    if http_client is not None:
        await _do_validate(http_client)
        return

    async with httpx.AsyncClient(timeout=60.0, http2=True) as client:
        await _do_validate(client)


async def make_alibaba_token_plan_request_non_streaming(
    req: AlibabaTokenPlanReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    with sentry_sdk.start_span(
        op="ai.request",
        description="Alibaba Personal Token Plan request",
    ) as span:
        span.set_tag("chat.model", req.model)
        try:
            response = await client.post(
                req.api_url,
                headers=req.headers,
                json=req.get_payload(),
                timeout=ALIBABA_TOKEN_PLAN_NON_STREAMING_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            content = message.get("content")
            if not isinstance(content, str):
                raise TypeError("missing response content")

            usage_data = data.get("usage")
            if usage_data and req.graph_id and req.node_id and not req.is_title_generation:
                await update_node_usage_data(
                    pg_engine=pg_engine,
                    graph_id=req.graph_id,
                    node_id=req.node_id,
                    usage_data=usage_data,
                    node_type=req.node_type,
                    model_id=req.model_id,
                )
            return content
        except HTTPStatusError as exc:
            error_message = _parse_alibaba_error(exc.response.content)
            logger.error(
                "HTTP error from Alibaba Personal Token Plan: status=%s message=%s",
                exc.response.status_code,
                error_message,
            )
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {exc.response.status_code}): {error_message}"
            ) from exc
        except (ConnectError, TimeoutException, AsyncTimeoutError) as exc:
            logger.error("Network/timeout error connecting to Alibaba Personal Token Plan")
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected Alibaba Personal Token Plan response for model=%s",
                _model_id(req.model),
                exc_info=True,
            )
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from exc


async def stream_alibaba_token_plan_response(
    req: AlibabaTokenPlanReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    from services.providers.openai_protocol import stream_openai_compatible_response

    req.validate_request()
    async for chunk in stream_openai_compatible_response(
        req,
        pg_engine,
        redis_manager,
        provider_label="Alibaba Personal Token Plan",
        error_parser=_parse_alibaba_error,
        final_data_container=final_data_container,
        span_description="Stream Alibaba Personal Token Plan response",
        on_rejected_request=_log_alibaba_rejected_request,
        preserve_reasoning_content=True,
    ):
        yield chunk
