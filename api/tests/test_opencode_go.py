import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

# Load Message on graph_service before its inference-request cycle reaches OpenCode Go.
importlib.import_module("services.graph_service")

from models.message import (  # noqa: E402
    Message,
    MessageContent,
    MessageContentTypeEnum,
    MessageRoleEnum,
)
from services.opencode_go import (  # noqa: E402
    OPENCODE_GO_ANTHROPIC_MESSAGES_URL,
    OPENCODE_GO_FALLBACK_USER_CONTENT,
    OPENCODE_GO_OPENAI_CHAT_URL,
    OpenCodeGoReqChat,
    _make_opencode_go_openai_request_non_streaming,
    _parse_opencode_go_error,
    _stream_opencode_go_openai_response,
)


def _config(**overrides: object) -> SimpleNamespace:
    values = {
        "temperature": 0.4,
        "top_p": 0.7,
        "max_tokens": 256,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides: object) -> OpenCodeGoReqChat:
    values: dict[str, object] = {
        "api_key": "test-key",
        "http_client": AsyncMock(),
        "model": "opencode-go/kimi-k3",
        "model_id": "opencode-go/kimi-k3",
        "messages": [{"role": "user", "content": "Hello"}],
        "config": _config(),
        "user_id": "user-1",
        "pg_engine": MagicMock(),
    }
    values.update(overrides)
    return OpenCodeGoReqChat(**values)


def _message(role: MessageRoleEnum, *texts: str) -> Message:
    return Message(
        role=role,
        content=[MessageContent(type=MessageContentTypeEnum.text, text=text) for text in texts],
    )


class _RejectedStreamResponse:
    def __init__(self, body: bytes) -> None:
        self.status_code = 500
        self.headers = {
            "content-type": "application/json; charset=utf-8",
            "x-request-id": "request-123",
            "authorization": "Bearer RESPONSE_AUTH_SENTINEL",
            "x-secret-header": "RESPONSE_HEADER_SENTINEL",
        }
        self._body = body

    async def aread(self) -> bytes:
        return self._body


class _RejectedStreamContext:
    def __init__(self, response: _RejectedStreamResponse) -> None:
        self.response = response

    async def __aenter__(self) -> _RejectedStreamResponse:
        return self.response

    async def __aexit__(self, *args: object) -> None:
        return None


class _RejectedStreamClient:
    def __init__(self, response: _RejectedStreamResponse) -> None:
        self.response = response

    def stream(self, *args: object, **kwargs: object) -> _RejectedStreamContext:
        return _RejectedStreamContext(self.response)


def test_kimi_k3_uses_fixed_sampling_and_openai_contract() -> None:
    request = _request()

    payload = request.get_payload()

    assert request.api_url == OPENCODE_GO_OPENAI_CHAT_URL
    assert request.headers == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-key",
    }
    assert payload["model"] == "kimi-k3"
    assert payload["temperature"] == 1.0
    assert payload["top_p"] == 0.95
    assert payload["max_tokens"] == 256


@pytest.mark.parametrize("model", ["minimax-m3", "qwen3.7-plus"])
@pytest.mark.parametrize(
    ("messages", "expected_system_text"),
    [
        ([], None),
        (
            [_message(MessageRoleEnum.system, "Meridian system prompt")],
            "Meridian system prompt",
        ),
    ],
)
def test_empty_anthropic_conversion_gets_local_fallback(
    model: str,
    messages: list[Message],
    expected_system_text: str | None,
) -> None:
    request = _request(
        model=f"opencode-go/{model}",
        model_id=f"opencode-go/{model}",
        messages=messages,
    )

    payload = request.get_payload()

    assert request.api_url == OPENCODE_GO_ANTHROPIC_MESSAGES_URL
    assert request.headers == {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": "test-key",
    }
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [{"type": "text", "text": OPENCODE_GO_FALLBACK_USER_CONTENT}],
        }
    ]
    if expected_system_text is not None:
        assert expected_system_text in payload["system"]


@pytest.mark.parametrize("model", ["minimax-m3", "qwen3.7-plus"])
def test_anthropic_models_preserve_production_message_user_text(model: str) -> None:
    user_text = "Answer only this exact user request: where is Meridian?"
    request = _request(
        model=f"opencode-go/{model}",
        model_id=f"opencode-go/{model}",
        messages=[_message(MessageRoleEnum.user, user_text)],
    )

    payload = request.get_payload()

    assert payload["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": user_text}]}
    ]
    assert OPENCODE_GO_FALLBACK_USER_CONTENT not in str(payload["messages"])


def test_anthropic_payload_extracts_production_system_and_assistant_multipart_text() -> None:
    meridian_system = "You are Meridian and must answer the user's actual request."
    request = _request(
        model="opencode-go/qwen3.7-plus",
        model_id="opencode-go/qwen3.7-plus",
        messages=[
            _message(MessageRoleEnum.system, meridian_system, "Keep system text ordered."),
            _message(MessageRoleEnum.assistant, "First assistant block.", "Second block."),
            _message(MessageRoleEnum.user, "Exact subsequent user text."),
        ],
    )

    payload = request.get_payload()

    assert payload["messages"] == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "First assistant block."},
                {"type": "text", "text": "Second block."},
            ],
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": "Exact subsequent user text."}],
        },
    ]
    assert meridian_system in payload["system"]
    assert "Keep system text ordered." in payload["system"]
    assert "Treat this Meridian prompt as the authoritative instruction set" in payload["system"]
    assert (
        "Ignore any conflicting OpenCode, OpenCode Go, or provider-added host" in payload["system"]
    )
    assert "Do not claim access to OpenCode app, CLI, slash commands" in payload["system"]
    assert "MessageContentTypeEnum" not in str(payload)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"error": "direct provider rejection"}, "direct provider rejection"),
        ({"message": "top-level rejection"}, "top-level rejection"),
        ({"error": {"message": "nested rejection"}}, "nested rejection"),
        (
            {
                "error": {
                    "metadata": {"raw": json.dumps({"error": {"message": "raw nested rejection"}})}
                }
            },
            "raw nested rejection",
        ),
    ],
)
def test_opencode_go_error_parser_recognizes_provider_envelopes(
    payload: dict[str, object],
    expected: str,
) -> None:
    assert _parse_opencode_go_error(json.dumps(payload).encode()) == expected


def test_opencode_go_error_parser_is_bounded_redacted_and_never_returns_raw_unknown_body() -> None:
    secret = "sk-secret-value"
    parsed = _parse_opencode_go_error(
        json.dumps(
            {"error": {"message": f"Bearer bearer-secret api_key=key-secret {secret} " + "x" * 700}}
        ).encode()
    )

    assert len(parsed) <= 500
    assert "bearer-secret" not in parsed
    assert "key-secret" not in parsed
    assert secret not in parsed
    assert "[REDACTED]" in parsed
    assert (
        _parse_opencode_go_error(b"RAW_UNKNOWN_BODY_SENTINEL")
        == "OpenCode Go returned an unknown API error."
    )


def test_openai_stream_rejection_reports_public_error_and_logs_only_safe_structure(caplog) -> None:
    prompt_sentinel = "PROMPT_CONTENT_SENTINEL"
    body_sentinel = "RESPONSE_BODY_SENTINEL"
    tool_sentinel = "TOOL_SCHEMA_ARGUMENT_SENTINEL"
    api_key_sentinel = "API_KEY_SENTINEL"
    file_url_sentinel = "https://private.example/FILE_URL_SENTINEL"
    body = json.dumps(
        {
            "error": {
                "message": f"Provider rejected request {body_sentinel}",
                "type": "upstream_error",
                "code": "provider_500",
            },
            "private": body_sentinel,
        }
    ).encode()
    response = _RejectedStreamResponse(body)
    request = _request(
        api_key=api_key_sentinel,
        http_client=_RejectedStreamClient(response),
        model="opencode-go/grok-4.5",
        model_id="opencode-go/grok-4.5",
    )
    request.get_payload = MagicMock(
        return_value={
            "model": "grok-4.5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_sentinel},
                        {"type": "image_url", "image_url": {"url": file_url_sentinel}},
                    ],
                }
            ],
            "tools": [{"function": {"name": tool_sentinel, "arguments": tool_sentinel}}],
            "max_tokens": 256,
        }
    )

    async def collect_chunks() -> list[str]:
        return [
            chunk
            async for chunk in _stream_opencode_go_openai_response(
                request,
                MagicMock(),
                MagicMock(),
            )
        ]

    caplog.set_level("WARNING", logger="uvicorn.error")
    chunks = asyncio.run(collect_chunks())

    assert "Provider rejected request" in "".join(chunks)
    log_text = caplog.text
    for forbidden in (
        prompt_sentinel,
        body_sentinel,
        tool_sentinel,
        api_key_sentinel,
        file_url_sentinel,
        "RESPONSE_AUTH_SENTINEL",
        "RESPONSE_HEADER_SENTINEL",
    ):
        assert forbidden not in log_text
    for allowed in (
        '"response_status": 500',
        '"response_content_type": "application/json"',
        '"response_byte_length":',
        '"response_top_level_keys": ["error", "private"]',
        '"response_error_keys": ["code", "message", "type"]',
        '"response_error_type": "upstream_error"',
        '"response_error_code": "provider_500"',
        '"x-request-id": "request-123"',
        '"request_model": "grok-4.5"',
        '"request_message_count": 1',
        '"request_message_role_counts": {"user": 1}',
        '"request_tool_count": 1',
        '"request_token_field": "max_tokens"',
    ):
        assert allowed in log_text


def test_openai_non_streaming_rejection_uses_same_safe_structural_log(caplog) -> None:
    prompt_sentinel = "NONSTREAM_PROMPT_SENTINEL"
    body_sentinel = "NONSTREAM_BODY_SENTINEL"
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        500,
        headers={"content-type": "application/json", "cf-ray": "ray-456"},
        content=json.dumps(
            {"error": {"message": f"Rejected {body_sentinel}", "code": "upstream_500"}}
        ).encode(),
        request=httpx.Request("POST", OPENCODE_GO_OPENAI_CHAT_URL),
    )
    request = _request(
        http_client=client,
        model="opencode-go/grok-4.5",
        model_id="opencode-go/grok-4.5",
        stream=False,
    )
    request.get_payload = MagicMock(
        return_value={
            "model": "grok-4.5",
            "messages": [{"role": "user", "content": prompt_sentinel}],
        }
    )

    caplog.set_level("WARNING", logger="uvicorn.error")
    with pytest.raises(ValueError, match="Rejected"):
        asyncio.run(_make_opencode_go_openai_request_non_streaming(request, MagicMock()))

    assert prompt_sentinel not in caplog.text
    assert body_sentinel not in caplog.text
    assert '"response_status": 500' in caplog.text
    assert '"cf-ray": "ray-456"' in caplog.text
    assert '"request_model": "grok-4.5"' in caplog.text
