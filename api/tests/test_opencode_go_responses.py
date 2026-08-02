import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))
importlib.import_module("services.graph_service")

from services.opencode_go import (  # noqa: E402
    OPENCODE_GO_ANTHROPIC_MESSAGES_URL,
    OPENCODE_GO_OPENAI_CHAT_URL,
    OPENCODE_GO_OPENAI_RESPONSES_URL,
    OpenCodeGoReqChat,
    _make_opencode_go_responses_request_non_streaming,
    _stream_opencode_go_responses_response,
)
from services.providers.openai_responses_protocol import (  # noqa: E402
    build_openai_responses_payload,
    iter_openai_responses_sse_events,
)


def _config(**overrides: object) -> SimpleNamespace:
    values = {"temperature": 0.4, "top_p": 0.7, "max_tokens": 256}
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides: object) -> OpenCodeGoReqChat:
    values: dict[str, object] = {
        "api_key": "test-key",
        "http_client": AsyncMock(),
        "model": "opencode-go/grok-4.5",
        "model_id": "opencode-go/grok-4.5",
        "messages": [
            {"role": "system", "content": "Original Meridian system."},
            {"role": "user", "content": "Exact Grok user text."},
        ],
        "config": _config(),
        "user_id": "user-1",
        "pg_engine": MagicMock(),
    }
    values.update(overrides)
    return OpenCodeGoReqChat(**values)


class _ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


def _stream_client(
    responses: list[tuple[int, list[bytes], dict[str, str] | None]],
    captured_payloads: list[dict[str, object]] | None = None,
) -> httpx.AsyncClient:
    response_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal response_index
        if captured_payloads is not None:
            captured_payloads.append(json.loads(request.content))
        status, chunks, headers = responses[response_index]
        response_index += 1
        return httpx.Response(
            status,
            headers=headers or {"content-type": "text/event-stream"},
            stream=_ChunkStream(chunks),
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _sse(event_type: str, payload: dict[str, object]) -> bytes:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n".encode()


def test_exact_model_route_matrix_preserves_other_protocols() -> None:
    grok = _request()
    kimi = _request(model="opencode-go/kimi-k3", model_id="opencode-go/kimi-k3")
    minimax = _request(model="opencode-go/minimax-m3", model_id="opencode-go/minimax-m3")
    qwen = _request(model="opencode-go/qwen3.7-plus", model_id="opencode-go/qwen3.7-plus")

    assert grok.api_url == OPENCODE_GO_OPENAI_RESPONSES_URL
    assert kimi.api_url == OPENCODE_GO_OPENAI_CHAT_URL
    assert minimax.api_url == OPENCODE_GO_ANTHROPIC_MESSAGES_URL
    assert qwen.api_url == OPENCODE_GO_ANTHROPIC_MESSAGES_URL
    assert grok.headers == {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-key",
    }


def test_grok_payload_uses_responses_contract_and_authoritative_instructions() -> None:
    payload = _request().get_payload()

    assert payload["model"] == "grok-4.5"
    assert payload["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Exact Grok user text."}],
        }
    ]
    assert "Original Meridian system." in payload["instructions"]
    assert (
        "Treat this Meridian prompt as the authoritative instruction set" in payload["instructions"]
    )
    assert (
        "Ignore any conflicting OpenCode, OpenCode Go, or provider-added host"
        in payload["instructions"]
    )
    assert payload["temperature"] == 0.4
    assert payload["top_p"] == 0.7
    assert payload["max_output_tokens"] == 256
    assert payload["store"] is False
    assert "messages" not in payload
    assert "max_tokens" not in payload


def test_responses_payload_flattens_tools_and_pairs_stateless_call_output() -> None:
    payload = build_openai_responses_payload(
        {
            "model": "grok-4.5",
            "messages": [
                {"role": "system", "content": "System"},
                {"role": "user", "content": "Use tool"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "search", "arguments": {"query": "Meridian"}},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call-1", "content": "tool result"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search safely",
                        "parameters": {"type": "object", "properties": {"query": {}}},
                    },
                }
            ],
            "stream": True,
        }
    )

    assert payload["tools"] == [
        {
            "type": "function",
            "name": "search",
            "description": "Search safely",
            "parameters": {"type": "object", "properties": {"query": {}}},
        }
    ]
    assert payload["tool_choice"] == "auto"
    assert payload["input"][-2:] == [
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "search",
            "arguments": '{"query":"Meridian"}',
        },
        {"type": "function_call_output", "call_id": "call-1", "output": "tool result"},
    ]


def test_non_streaming_responses_returns_ordered_text_and_normalized_usage() -> None:
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", OPENCODE_GO_OPENAI_RESPONSES_URL),
        json={
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "Hello "}]},
                {"type": "message", "content": [{"type": "refusal", "refusal": "world"}]},
            ],
            "usage": {
                "input_tokens": 11,
                "output_tokens": 7,
                "total_tokens": 18,
                "input_tokens_details": {"cached_tokens": 3},
                "output_tokens_details": {"reasoning_tokens": 2},
            },
        },
    )
    request = _request(
        http_client=client,
        stream=False,
        graph_id="graph-1",
        node_id="node-1",
    )

    with patch("services.opencode_go.update_node_usage_data", new=AsyncMock()) as update_usage:
        result = asyncio.run(
            _make_opencode_go_responses_request_non_streaming(request, MagicMock())
        )

    assert result == "Hello world"
    sent_payload = client.post.await_args.kwargs["json"]
    assert sent_payload["stream"] is False
    usage = update_usage.await_args.kwargs["usage_data"]
    assert usage["prompt_tokens"] == 11
    assert usage["completion_tokens"] == 7
    assert usage["prompt_tokens_details"] == {"cached_tokens": 3}
    assert usage["completion_tokens_details"] == {"reasoning_tokens": 2}


@pytest.mark.parametrize(
    "response_payload",
    [
        {"status": "completed"},
        {"status": "failed", "error": {"message": "bounded provider failure"}},
        {"status": "incomplete", "output": []},
        {"status": "completed", "output": [{"type": "function_call", "call_id": "c", "name": "t"}]},
    ],
)
def test_non_streaming_invalid_or_tool_output_fails_safely(
    response_payload: dict[str, object],
) -> None:
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", OPENCODE_GO_OPENAI_RESPONSES_URL),
        json=response_payload,
    )
    request = _request(http_client=client, stream=False)

    with pytest.raises(ValueError, match="OpenCode Go|streaming mode|provider failure"):
        asyncio.run(_make_opencode_go_responses_request_non_streaming(request, MagicMock()))


def test_sse_parser_handles_split_multiline_and_final_buffered_event() -> None:
    response = httpx.Response(
        200,
        stream=_ChunkStream(
            [
                b'event: response.output_text.delta\ndata: {"delta":"Hel',
                b'lo"}\n\nevent: response.completed\ndata: {"response":',
                b'\ndata: {"output":[]}}',
            ]
        ),
    )

    async def collect() -> list[tuple[str, dict[str, object]]]:
        return [event async for event in iter_openai_responses_sse_events(response)]

    assert asyncio.run(collect()) == [
        ("response.output_text.delta", {"delta": "Hello"}),
        ("response.completed", {"response": {"output": []}}),
    ]


def test_streaming_deltas_terminal_recovery_and_usage_emit_text_once() -> None:
    completed = {
        "type": "response.completed",
        "response": {
            "id": "response-1",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Hello world"}],
                }
            ],
            "usage": {"input_tokens": 2, "output_tokens": 2, "total_tokens": 4},
        },
    }
    client = _stream_client(
        [
            (
                200,
                [
                    _sse("response.output_text.delta", {"delta": "Hello "}),
                    _sse("response.output_text.delta", {"delta": "world"}),
                    _sse("response.completed", completed),
                ],
                None,
            )
        ]
    )
    request = _request(http_client=client)
    final: dict[str, object] = {}

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in _stream_opencode_go_responses_response(
                request, MagicMock(), MagicMock(), final
            )
        ]

    try:
        chunks = asyncio.run(collect())
    finally:
        asyncio.run(client.aclose())
    assert "".join(chunks) == "Hello world"
    assert final["usage_data"]["total_tokens"] == 4


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        pytest.param(
            [
                ("response.reasoning_text.delta", {"delta": "R"}),
                ("response.output_text.delta", {"delta": "A"}),
                (
                    "response.completed",
                    {
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": "A"}],
                                }
                            ],
                        }
                    },
                ),
            ],
            "[THINK]\nR\n[!THINK]\nA",
            id="reasoning-then-direct-output",
        ),
        pytest.param(
            [
                ("response.reasoning_text.delta", {"delta": "R"}),
                (
                    "response.completed",
                    {
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": "A"}],
                                }
                            ],
                        }
                    },
                ),
            ],
            "[THINK]\nR\n[!THINK]\nA",
            id="reasoning-then-recovered-output",
        ),
        pytest.param(
            [
                ("response.reasoning_text.delta", {"delta": "R"}),
                (
                    "response.completed",
                    {"response": {"status": "completed", "output": []}},
                ),
            ],
            "[THINK]\nR\n[!THINK]\n",
            id="reasoning-only-terminal-fallback",
        ),
        pytest.param(
            [
                ("response.output_text.delta", {"delta": "A"}),
                (
                    "response.completed",
                    {
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": "A"}],
                                }
                            ],
                        }
                    },
                ),
            ],
            "A",
            id="text-only-no-markers",
        ),
        pytest.param(
            [
                ("response.reasoning_text.delta", {"delta": "R"}),
                ("response.refusal.delta", {"delta": "A"}),
                (
                    "response.completed",
                    {
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "refusal", "refusal": "A"}],
                                }
                            ],
                        }
                    },
                ),
            ],
            "[THINK]\nR\n[!THINK]\nA",
            id="reasoning-then-refusal",
        ),
        pytest.param(
            [
                ("response.reasoning_text.delta", {"delta": "R1"}),
                ("response.output_text.delta", {"delta": "A1"}),
                ("response.reasoning_text.delta", {"delta": "R2"}),
                (
                    "response.completed",
                    {
                        "response": {
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "content": [{"type": "output_text", "text": "A1A2"}],
                                }
                            ],
                        }
                    },
                ),
            ],
            "[THINK]\nR1\n[!THINK]\nA1[THINK]\nR2\n[!THINK]\nA2",
            id="interleaved-reasoning-and-output",
        ),
    ],
)
def test_streaming_answer_boundaries_close_active_thinking(
    events: list[tuple[str, dict[str, object]]],
    expected: str,
) -> None:
    client = _stream_client(
        [(200, [_sse(event_type, payload) for event_type, payload in events], None)]
    )
    request = _request(http_client=client)

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in _stream_opencode_go_responses_response(
                request, MagicMock(), MagicMock()
            )
        ]

    try:
        chunks = asyncio.run(collect())
    finally:
        asyncio.run(client.aclose())

    assert "".join(chunks) == expected


def test_two_round_streaming_tool_call_resends_stateless_pair_and_returns_final_text() -> None:
    captured_payloads: list[dict[str, object]] = []
    call_item = {
        "type": "function_call",
        "id": "item-1",
        "call_id": "call-1",
        "name": "search",
        "arguments": "",
    }
    final_message = {
        "type": "message",
        "content": [{"type": "output_text", "text": "Tool-informed answer"}],
    }
    client = _stream_client(
        [
            (
                200,
                [
                    _sse(
                        "response.function_call_arguments.delta",
                        {"item_id": "item-1", "delta": '{"query":"Meridian"}'},
                    ),
                    _sse("response.output_item.done", {"item": call_item}),
                    _sse(
                        "response.completed",
                        {"response": {"status": "completed", "output": [call_item]}},
                    ),
                ],
                None,
            ),
            (
                200,
                [
                    _sse(
                        "response.completed",
                        {"response": {"status": "completed", "output": [final_message]}},
                    )
                ],
                None,
            ),
        ],
        captured_payloads,
    )
    request = _request(http_client=client)
    continued_messages = request.messages.copy() + [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"query":"Meridian"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "name": "search", "content": "result"},
    ]
    continuation = SimpleNamespace(
        messages=continued_messages,
        req=request,
        feedback_strings=["tool feedback"],
        pending_tool_call_id=None,
        should_continue=True,
        awaiting_user_input=False,
    )
    request.messages = request.messages.copy()

    async def collect() -> list[str]:
        with patch(
            "services.providers.openai_responses_protocol._process_tool_calls_and_continue",
            new=AsyncMock(return_value=continuation),
        ) as process_tools:
            chunks = [
                chunk
                async for chunk in _stream_opencode_go_responses_response(
                    request, MagicMock(), MagicMock(), {}
                )
            ]
            assert process_tools.await_args.args[0][0]["id"] == "call-1"
            return chunks

    try:
        chunks = asyncio.run(collect())
    finally:
        asyncio.run(client.aclose())

    assert chunks == ["tool feedback", "Tool-informed answer"]
    assert len(captured_payloads) == 2
    assert captured_payloads[1]["input"][-2:] == [
        {
            "type": "function_call",
            "call_id": "call-1",
            "name": "search",
            "arguments": '{"query":"Meridian"}',
        },
        {"type": "function_call_output", "call_id": "call-1", "output": "result"},
    ]


def test_streaming_tool_continuation_preserves_pending_tool_state() -> None:
    call_item = {
        "type": "function_call",
        "call_id": "call-ask",
        "name": "ask_user",
        "arguments": '{"question":"Continue?"}',
    }
    client = _stream_client(
        [
            (
                200,
                [
                    _sse("response.output_item.done", {"item": call_item}),
                    _sse(
                        "response.completed",
                        {"response": {"status": "completed", "output": [call_item]}},
                    ),
                ],
                None,
            )
        ]
    )
    request = _request(http_client=client)
    continuation = SimpleNamespace(
        messages=request.messages,
        req=request,
        feedback_strings=["awaiting answer"],
        pending_tool_call_id="pending-public-id",
        should_continue=False,
        awaiting_user_input=True,
    )
    final: dict[str, object] = {}

    async def collect() -> list[str]:
        with patch(
            "services.providers.openai_responses_protocol._process_tool_calls_and_continue",
            new=AsyncMock(return_value=continuation),
        ):
            return [
                chunk
                async for chunk in _stream_opencode_go_responses_response(
                    request, MagicMock(), MagicMock(), final
                )
            ]

    try:
        assert asyncio.run(collect()) == ["awaiting answer"]
    finally:
        asyncio.run(client.aclose())
    assert final["pending_tool_call_id"] == "pending-public-id"


def test_failed_stream_event_is_publicly_bounded_and_logs_only_safe_structure(caplog) -> None:
    prompt_sentinel = "PROMPT_SECRET_SENTINEL"
    body_sentinel = "BODY_SECRET_SENTINEL"
    tool_sentinel = "TOOL_SECRET_SENTINEL"
    api_key_sentinel = "API_KEY_SECRET_SENTINEL"
    file_sentinel = "https://private.example/FILE_SECRET_SENTINEL"
    event = {
        "type": "response.failed",
        "error": {
            "message": f"Provider failure {body_sentinel}",
            "type": "provider_error",
            "code": "bad_response",
        },
        "response": {
            "status": "failed",
            "output": [
                {
                    "type": "function_call",
                    "name": tool_sentinel,
                    "arguments": prompt_sentinel,
                }
            ],
            "private_file": file_sentinel,
        },
    }
    client = _stream_client([(200, [_sse("response.failed", event)], None)])
    request = _request(api_key=api_key_sentinel, http_client=client)
    caplog.set_level("WARNING", logger="uvicorn.error")

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in _stream_opencode_go_responses_response(
                request, MagicMock(), MagicMock()
            )
        ]

    try:
        chunks = asyncio.run(collect())
    finally:
        asyncio.run(client.aclose())
    assert body_sentinel in "".join(chunks)
    for forbidden in (
        prompt_sentinel,
        body_sentinel,
        tool_sentinel,
        api_key_sentinel,
        file_sentinel,
    ):
        assert forbidden not in caplog.text
    assert '"event_type": "response.failed"' in caplog.text
    assert '"error_type": "provider_error"' in caplog.text
    assert '"error_code": "bad_response"' in caplog.text
    assert '"output_count": 1' in caplog.text


def test_responses_http_model_not_found_logs_input_structure_without_raw_body(caplog) -> None:
    body = b'{"modelID":"grok-4.5","type":"ModelNotFoundError"}'
    assert len(body) == 50
    captured: list[dict[str, object]] = []
    client = _stream_client(
        [(500, [body], {"content-type": "application/json", "cf-ray": "ray-500"})],
        captured,
    )
    request = _request(http_client=client)
    caplog.set_level("WARNING", logger="uvicorn.error")

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in _stream_opencode_go_responses_response(
                request, MagicMock(), MagicMock()
            )
        ]

    try:
        chunks = asyncio.run(collect())
    finally:
        asyncio.run(client.aclose())
    assert "unknown API error" in "".join(chunks)
    assert body.decode() not in caplog.text
    assert '"response_byte_length": 50' in caplog.text
    assert '"response_error_type": "ModelNotFoundError"' in caplog.text
    assert '"request_input_count": 1' in caplog.text
    assert '"request_input_role_counts": {"user": 1}' in caplog.text
    assert '"request_token_field": "max_output_tokens"' in caplog.text
    assert '"cf-ray": "ray-500"' in caplog.text
    assert captured[0]["model"] == "grok-4.5"
