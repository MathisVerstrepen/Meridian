import logging
from asyncio import TimeoutError as AsyncTimeoutError
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import sentry_sdk
from database.pg.graph_ops.graph_node_crud import update_node_usage_data
from database.redis.redis_ops import RedisManager
from httpx import ConnectError, HTTPStatusError, TimeoutException
from models.message import ToolEnum
from services.openrouter import _parse_openrouter_error
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
from services.providers.openai_protocol import (
    normalize_openai_request_message,
    sanitize_openai_messages,
    stream_openai_compatible_response,
)
from services.providers.z_ai_coding_plan_catalog import Z_AI_CODING_PLAN_MODEL_PREFIX
from services.tools import get_openrouter_tools
from sqlalchemy.ext.asyncio import AsyncEngine as SQLAlchemyAsyncEngine

logger = logging.getLogger("uvicorn.error")

Z_AI_CODING_PLAN_CHAT_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
Z_AI_CODING_PLAN_VALIDATION_MODEL = f"{Z_AI_CODING_PLAN_MODEL_PREFIX}glm-5.1"
Z_AI_CODING_PLAN_NON_STREAMING_TIMEOUT = httpx.Timeout(300.0, connect=10.0, read=300.0)
Z_AI_TOOL_CALL_PLACEHOLDER_CONTENT = "[Tool call issued]"
Z_AI_FALLBACK_USER_CONTENT = "Please respond to the available context."


def _build_thinking_payload(config: Any, is_title_generation: bool) -> dict[str, str]:
    if is_title_generation or bool(getattr(config, "exclude_reasoning", False)):
        return {"type": "disabled"}
    return {"type": "enabled"}


class ZAiCodingPlanReq:
    BASE_HEADERS = {
        "Content-Type": "application/json",
    }

    def __init__(
        self,
        api_key: str,
        api_url: str = Z_AI_CODING_PLAN_CHAT_URL,
        http_client=None,
    ):
        self.api_key = api_key
        self.z_ai_api_key = api_key
        self.headers = {**self.BASE_HEADERS, "Authorization": f"Bearer {api_key}"}
        self.api_url = api_url
        self.http_client = http_client


@dataclass(kw_only=True)
class ZAiCodingPlanReqChat(BaseProviderReq, ZAiCodingPlanReq):
    api_key: str
    http_client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        ZAiCodingPlanReq.__init__(self, api_key=self.api_key, http_client=self.http_client)
        if self.http_client is None:
            raise ValueError("http_client must be provided")

    def validate_request(self) -> None:
        if self.schema is not None:
            raise ValueError(
                "Z.AI Coding Plan models do not support structured-output helpers yet."
            )

        validate_supported_tools("Z.AI Coding Plan", self.selected_tools)

        if self.file_uuids or self.file_hashes or has_file_attachments(self.messages):
            raise ValueError(
                "Z.AI Coding Plan models do not support attachments or PDF parsing yet."
            )

        validate_http_client_for_tools("Z.AI Coding Plan", self.selected_tools, self.http_client)

    def get_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": strip_model_prefix(self.model, Z_AI_CODING_PLAN_MODEL_PREFIX),
            "messages": self._build_request_messages(),
            "stream": self.stream,
            "temperature": normalize_temperature(getattr(self.config, "temperature", None)),
            "top_p": normalize_top_p(getattr(self.config, "top_p", None)),
            "max_tokens": normalize_max_tokens(getattr(self.config, "max_tokens", None)),
            "thinking": _build_thinking_payload(self.config, self.is_title_generation),
        }

        tools = get_openrouter_tools(self.selected_tools)
        if tools:
            payload["tools"] = tools

        return {key: value for key, value in payload.items() if value is not None}

    def _build_request_messages(self) -> list[dict[str, Any]]:
        normalized_messages = [
            normalize_openai_request_message(
                raw_message,
                include_reasoning_content=True,
                strip_text=False,
            )
            for raw_message in self.messages
        ]
        return sanitize_openai_messages(
            normalized_messages,
            fallback_user_content=Z_AI_FALLBACK_USER_CONTENT,
            provider_label="Z.AI Coding Plan",
            tool_call_placeholder_content=Z_AI_TOOL_CALL_PLACEHOLDER_CONTENT,
        )


def _log_z_ai_rejected_request(req: ZAiCodingPlanReqChat) -> None:
    logger.error(
        "Z.AI Coding Plan rejected request with messages=%s",
        [
            {
                "role": str(message.get("role") or ""),
                "content_length": len(str(message.get("content") or "")),
                "has_tool_calls": bool(message.get("tool_calls")),
                "tool_call_id": str(message.get("tool_call_id") or ""),
            }
            for message in req._build_request_messages()
        ],
    )


async def validate_z_ai_coding_plan_api_key(
    api_key: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    payload = {
        "model": strip_model_prefix(
            Z_AI_CODING_PLAN_VALIDATION_MODEL, Z_AI_CODING_PLAN_MODEL_PREFIX
        ),
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "stream": False,
        "max_tokens": 16,
        "thinking": {"type": "disabled"},
    }

    async def _do_validate(client: httpx.AsyncClient) -> None:
        response = await client.post(
            Z_AI_CODING_PLAN_CHAT_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        if response.status_code != 200:
            error_message = _parse_openrouter_error(response.content)
            raise ValueError(
                f"Z.AI Coding Plan validation failed (status {response.status_code}): "
                f"{error_message}"
            )

    if http_client is not None:
        await _do_validate(http_client)
        return

    async with httpx.AsyncClient(timeout=60.0, http2=True) as client:
        await _do_validate(client)


async def make_z_ai_coding_plan_request_non_streaming(
    req: ZAiCodingPlanReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
) -> str:
    req.validate_request()
    if ToolEnum.ASK_USER in req.selected_tools:
        raise ValueError("Z.AI Coding Plan ask_user requires streaming mode.")

    client = req.http_client
    if client is None:
        raise ValueError("http_client must be provided")

    with sentry_sdk.start_span(op="ai.request", description="Z.AI Coding Plan request") as span:
        span.set_tag("chat.model", req.model)
        try:
            response = await client.post(
                req.api_url,
                headers=req.headers,
                json=req.get_payload(),
                timeout=Z_AI_CODING_PLAN_NON_STREAMING_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]
            content = str(message.get("content") or "")

            if usage_data := data.get("usage"):
                if req.graph_id and req.node_id and not req.is_title_generation:
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
            error_message = _parse_openrouter_error(exc.response.content)
            logger.error(
                "HTTP error from Z.AI Coding Plan: %s - %s",
                exc.response.status_code,
                error_message,
            )
            span.set_status("internal_error")
            raise ValueError(
                f"API Error (Status: {exc.response.status_code}): {error_message}"
            ) from exc
        except (ConnectError, TimeoutException, AsyncTimeoutError) as exc:
            logger.error("Network/Timeout error connecting to Z.AI Coding Plan: %s", exc)
            span.set_status("unavailable")
            raise ConnectionError(
                "Could not connect to the AI service. Please check your network."
            ) from exc
        except Exception as exc:
            logger.error(
                "An unexpected error occurred during Z.AI Coding Plan request: %s",
                exc,
                exc_info=True,
            )
            span.set_status("internal_error")
            raise RuntimeError("An unexpected server error occurred.") from exc


async def stream_z_ai_coding_plan_response(
    req: ZAiCodingPlanReqChat,
    pg_engine: SQLAlchemyAsyncEngine,
    redis_manager: RedisManager,
    final_data_container: Optional[dict[str, Any]] = None,
):
    req.validate_request()
    async for chunk in stream_openai_compatible_response(
        req,
        pg_engine,
        redis_manager,
        provider_label="Z.AI Coding Plan",
        error_parser=_parse_openrouter_error,
        final_data_container=final_data_container,
        span_description="Stream Z.AI Coding Plan response",
        on_rejected_request=_log_z_ai_rejected_request,
    ):
        yield chunk
