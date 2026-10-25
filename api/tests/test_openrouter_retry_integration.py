"""Exercise the real orchestration functions without importing provider runtime cycles."""

import ast
import asyncio
import json
import logging
import sys
from contextlib import aclosing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from services import openrouter_retry as retry
from services.openrouter_transport import post_openrouter_json, stream_openrouter_data
from services.stream_retry_status import retry_status_sender
from services.usage_data import (
    append_usage_request_breakdown,
    build_usage_request_breakdown,
    finalize_usage_data,
)


def load_functions():
    # Match the repository's isolated OpenRouter tests: the full module imports all runtimes.
    path = Path(__file__).resolve().parents[1] / "app/services/openrouter.py"
    source = ast.parse(path.read_text())
    names = {
        "stream_openrouter_response",
        "make_openrouter_request_non_streaming",
        "_process_chunk",
    }
    module = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            *(
                node
                for node in source.body
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in names
            ),
        ],
        type_ignores=[],
    )
    namespace = {
        "asyncio": asyncio,
        "aclosing": aclosing,
        "json": json,
        "logger": logging.getLogger(__name__),
        "sentry_sdk": MagicMock(),
        "OpenRouterError": retry.OpenRouterError,
        "stream_openrouter_data": stream_openrouter_data,
        "post_openrouter_json": post_openrouter_json,
        "_process_tool_calls_and_continue": AsyncMock(),
        "_merge_tool_call_chunks": lambda chunks: chunks,
        "extract_tool_names": lambda chunks: ["web_search"] if chunks else [],
        "append_usage_request_breakdown": append_usage_request_breakdown,
        "build_usage_request_breakdown": build_usage_request_breakdown,
        "finalize_usage_data": finalize_usage_data,
        "update_node_usage_data": AsyncMock(),
        "ConnectError": httpx.ConnectError,
        "TimeoutException": httpx.TimeoutException,
        "AsyncTimeoutError": asyncio.TimeoutError,
        "HTTPStatusError": httpx.HTTPStatusError,
    }
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


def event(delta=None, finish=None, **extra):
    return {"choices": [{"delta": delta or {}, "finish_reason": finish}], **extra}


def response(*events):
    return httpx.Response(
        200,
        content="".join(
            f"data: {json.dumps(value) if isinstance(value, dict) else value}\n\n"
            for value in events
        ),
        headers={"content-type": "text/event-stream"},
    )


def request(client, payload):
    return SimpleNamespace(
        http_client=client,
        api_url="https://openrouter.ai/api/v1/chat/completions",
        headers={},
        get_payload=lambda: payload,
        messages=[],
        model="test-model",
        node_id="node",
        graph_id="graph",
        model_id=None,
        node_type="text_to_text",
        is_title_generation=False,
    )


@pytest.mark.parametrize("continuation_fails", [False, True])
def test_retries_do_not_repeat_completed_tools_or_usage(monkeypatch, continuation_fails):
    async def run():
        monkeypatch.setattr(retry.asyncio, "sleep", AsyncMock())
        ns = load_functions()
        tool = {"index": 0, "id": "tool-1", "function": {"name": "web_search", "arguments": "{}"}}
        first = response(
            event(
                {"tool_calls": [tool]},
                finish="tool_calls",
                usage={
                    "prompt_tokens": 2,
                    "completion_tokens": 3,
                    "total_tokens": 5,
                },
                id="tool-request",
            ),
            "[DONE]",
        )
        responses = [first, httpx.Response(429, json={"error": {"message": "busy"}})]
        if continuation_fails:
            responses += [
                httpx.Response(429, json={"error": {"message": "busy"}}) for _ in range(3)
            ]
        else:
            responses.append(
                response(
                    event(
                        {"content": "Answer"},
                        finish="stop",
                        usage={
                            "prompt_tokens": 4,
                            "completion_tokens": 6,
                            "total_tokens": 10,
                        },
                        id="answer-request",
                    ),
                    "[DONE]",
                )
            )
        sent_payloads = []

        def respond(req):
            sent_payloads.append(json.loads(req.content))
            return responses.pop(0)

        final = {}
        notices = AsyncMock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            initial = request(client, {"messages": [{"role": "user", "content": "Search"}]})
            continued_payload = {"messages": [{"role": "tool", "content": "Saved result"}]}
            continued = request(client, continued_payload)

            async def execute_once(*args, **kwargs):
                assert first.is_closed, "The tool must run after the provider response closes"
                return SimpleNamespace(
                    req=continued,
                    messages=[],
                    feedback_strings=["Tool completed"],
                    should_continue=True,
                    pending_tool_call_id=None,
                    awaiting_user_input=False,
                )

            ns["_process_tool_calls_and_continue"].side_effect = execute_once
            output = [
                chunk
                async for chunk in ns["stream_openrouter_response"](
                    initial, None, None, final, on_retry=notices
                )
            ]
        ns["_process_tool_calls_and_continue"].assert_awaited_once()
        assert output.count("Tool completed") == 1
        assert all(payload == continued_payload for payload in sent_payloads[1:])
        if continuation_fails:
            assert sum("[ERROR]" in chunk for chunk in output) == 1
            assert final["usage_data"]["total_tokens"] == 5
        else:
            assert "Answer" in output
            assert not any("[ERROR]" in chunk for chunk in output)
            assert final["usage_data"]["total_tokens"] == 15
        assert notices.await_args_list[-1].args == (None,)

    asyncio.run(run())


def test_terminal_stream_error_preserves_partial_text_and_closes_reasoning(monkeypatch):
    async def run():
        sleep = AsyncMock()
        monkeypatch.setattr(retry.asyncio, "sleep", sleep)
        ns = load_functions()
        failed = response(
            event({"reasoning": "Thinking"}), {"error": {"code": 429, "message": "busy"}}
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: failed)) as client:
            output = [
                chunk
                async for chunk in ns["stream_openrouter_response"](request(client, {}), None, None)
            ]
        assert output == ["[THINK]\nThinking", "\n[!THINK]\n", "[ERROR]Stream Error: busy[!ERROR]"]
        sleep.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.parametrize("persist_fails", [False, True])
def test_non_streaming_usage_write_is_outside_retry_boundary(monkeypatch, persist_fails):
    async def run():
        monkeypatch.setattr(retry.asyncio, "sleep", AsyncMock())
        ns = load_functions()
        responses = [
            httpx.Response(503),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"total_tokens": 5},
                },
            ),
        ]
        if persist_fails:
            ns["update_node_usage_data"].side_effect = RuntimeError("database unavailable")
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            req = request(c, {})
            if persist_fails:
                with pytest.raises(RuntimeError):
                    await ns["make_openrouter_request_non_streaming"](req, None)
            else:
                assert await ns["make_openrouter_request_non_streaming"](req, None) == "ok"
        ns["update_node_usage_data"].assert_awaited_once()
        assert not responses

    asyncio.run(run())


def test_websocket_status_is_separate_from_generated_content():
    async def run():
        websocket = SimpleNamespace(send_json=AsyncMock())
        send = retry_status_sender(websocket, "node", "model")
        await send(retry.RetryStatus(2, 4, 3.5))
        await send(None)
        status, cleared = [call.args[0] for call in websocket.send_json.await_args_list]
        assert status["type"] == "stream_retry_status"
        assert status["model_id"] == "model"
        assert status["payload"]["attempt"] == 2
        assert "4 seconds" in status["payload"]["message"]
        assert cleared == {
            "type": "stream_retry_status",
            "node_id": "node",
            "model_id": "model",
            "payload": None,
        }

    asyncio.run(run())
