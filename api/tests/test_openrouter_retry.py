import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from services import openrouter_retry as retry
from services.openrouter_transport import post_openrouter_json, stream_openrouter_data

URL = "https://openrouter.ai/api/v1/chat/completions"


def frame(delta=None, *, finish=None, **extra):
    return json.dumps({"choices": [{"delta": delta or {}, "finish_reason": finish}], **extra})


def sse(*events):
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content="".join(f"data: {event}\n\n" for event in events),
    )


async def collect(client, on_retry=None):
    return [
        data
        async for data in stream_openrouter_data(
            client, URL, {}, {"model": "test"}, on_retry=on_retry
        )
    ]


@pytest.fixture
def sleeps(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(retry.asyncio, "sleep", sleep)
    monkeypatch.setattr(retry.random, "uniform", lambda low, high: high)
    return sleep


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_http_errors_retry_and_close_before_notifying(status, sleeps):
    async def run():
        failed = httpx.Response(status, json={"error": {"code": status, "message": "busy"}})
        responses = [failed, sse(frame({"content": "Hello"}), "[DONE]")]
        notices = []

        async def notify(value):
            assert failed.is_closed
            notices.append(value)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            result = await collect(c, notify)
        assert result == [frame({"content": "Hello"}), "[DONE]"]
        assert notices == [retry.RetryStatus(2, 4, 2), None]
        sleeps.assert_awaited_once_with(2)

    asyncio.run(run())


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
def test_permanent_failures_never_retry(status, sleeps):
    async def run():
        response = httpx.Response(status, json={"error": {"message": "permanent"}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: response)) as c:
            with pytest.raises(retry.OpenRouterError, match="permanent"):
                await collect(c)
        sleeps.assert_not_awaited()

    asyncio.run(run())


def test_exhaustion_uses_exponential_backoff_and_only_four_attempts(sleeps):
    async def run():
        requests = []

        def respond(req):
            requests.append(req)
            return httpx.Response(429, json={"error": {"message": "Resource exhausted"}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
            with pytest.raises(retry.OpenRouterError, match="Resource exhausted"):
                await collect(c)
        assert len(requests) == 4
        assert [call.args[0] for call in sleeps.await_args_list] == [2, 4, 8]

    asyncio.run(run())


def test_retry_after_is_a_minimum_and_total_wait_is_bounded(sleeps):
    async def run():
        requests = []

        def respond(req):
            requests.append(req)
            return httpx.Response(
                429, headers={"retry-after": "50"}, json={"error": {"message": "busy"}}
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
            with pytest.raises(retry.OpenRouterError):
                await collect(c)
        assert len(requests) == 2
        sleeps.assert_awaited_once_with(50)

    asyncio.run(run())


def test_retry_after_longer_than_budget_does_not_retry_early(sleeps):
    error = retry.normalize_openrouter_error(
        {"error": {"code": 429}}, headers={"retry-after": "120"}
    )
    assert retry.RetryBudget().delay(error, 1) is None


def test_retry_after_supports_dates_and_ignores_invalid_values():
    date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60), usegmt=True)
    assert 58 <= retry.parse_retry_after(date) <= 60
    for value in [None, "oops", "NaN", "Infinity"]:
        assert retry.parse_retry_after(value) is None
    assert retry.parse_retry_after("-10") == 0


def test_jitter_stays_inside_exponential_window(monkeypatch):
    calls = []
    monkeypatch.setattr(retry.random, "uniform", lambda lo, hi: calls.append((lo, hi)) or hi / 2)
    budget = retry.RetryBudget()
    error = retry.OpenRouterError("busy", status_code=429)
    assert [budget.delay(error, i) for i in [1, 2, 3]] == [1, 2, 4]
    assert calls == [(0, 2), (0, 4), (0, 8)]


def test_provider_metadata_is_preserved_without_message_based_classification():
    error = retry.normalize_openrouter_error(
        {
            "id": "gen-1",
            "error": {
                "code": "429",
                "message": "Provider failed",
                "metadata": {"raw": json.dumps({"error": {"message": "Resource exhausted"}})},
            },
        }
    )
    assert str(error) == "Resource exhausted"
    assert error.status_code == 429
    assert error.request_id == "gen-1"
    assert error.metadata["raw"]
    assert error.retryable
    permanent = retry.normalize_openrouter_error(
        {"error": {"code": 429, "message": "429 busy"}}, status_code=401
    )
    assert not permanent.retryable
    plain = retry.normalize_openrouter_error(b"Service unavailable", status_code=503)
    assert str(plain) == "Service unavailable"
    assert plain.retryable


def test_temporary_budget_402_requires_both_metadata_and_retry_after():
    payload = {"error": {"code": 402, "metadata": {"limit_source": "openrouter_in_flight_budget"}}}
    assert retry.normalize_openrouter_error(payload, headers={"retry-after": "5"}).retryable
    assert not retry.normalize_openrouter_error(payload).retryable
    assert not retry.normalize_openrouter_error(
        {"error": {"code": 402}}, headers={"retry-after": "5"}
    ).retryable


def test_sse_error_before_output_discards_failed_attempt_state(sleeps):
    async def run():
        responses = [
            sse(
                frame({"role": "assistant"}, id="failed-id", usage={"total_tokens": 10}),
                json.dumps({"error": {"code": 429, "message": "busy"}}),
            ),
            sse(frame({"content": "ok"}, id="success-id"), "[DONE]"),
        ]
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            result = await collect(c)
        assert result == [frame({"content": "ok"}, id="success-id"), "[DONE]"]
        sleeps.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "delta",
    [
        {"content": "partial"},
        {"reasoning": "thinking"},
        {"reasoning_details": [{"text": "thinking"}]},
        {"tool_calls": [{"index": 0, "function": {"name": "execute_code"}}]},
    ],
)
def test_sse_error_after_meaningful_output_never_retries(delta, sleeps):
    async def run():
        response = sse(frame(delta), json.dumps({"error": {"code": 503, "message": "overload"}}))
        output = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: response)) as c:
            with pytest.raises(retry.OpenRouterError, match="overload"):
                async for data in stream_openrouter_data(c, URL, {}, {}):
                    output.append(data)
        assert output == [frame(delta)]
        sleeps.assert_not_awaited()

    asyncio.run(run())


class BrokenStream(httpx.AsyncByteStream):
    def __init__(self, prefix=b""):
        self.prefix = prefix
        self.closed = False

    async def __aiter__(self):
        if self.prefix:
            yield self.prefix
        raise httpx.ReadError("connection dropped")

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("partial", [False, True])
def test_disconnect_retries_only_before_output(partial, sleeps):
    async def run():
        prefix = f'data: {frame({"content": "partial"})}\n\n'.encode() if partial else b""
        broken = BrokenStream(prefix)
        responses = [httpx.Response(200, stream=broken), sse(frame({"content": "ok"}), "[DONE]")]
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            if partial:
                with pytest.raises(retry.OpenRouterError):
                    await collect(c)
                sleeps.assert_not_awaited()
            else:
                assert await collect(c) == [frame({"content": "ok"}), "[DONE]"]
                sleeps.assert_awaited_once()
        assert broken.closed

    asyncio.run(run())


def test_cancellation_during_backoff_clears_status_and_stops(monkeypatch):
    async def run():
        waiting = asyncio.Event()
        notices = []
        requests = []

        async def sleep(delay):
            waiting.set()
            await asyncio.Event().wait()

        async def notify(value):
            notices.append(value)

        def respond(req):
            requests.append(req)
            return httpx.Response(429, json={"error": {"message": "busy"}})

        monkeypatch.setattr(retry.asyncio, "sleep", sleep)
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as c:
            task = asyncio.create_task(collect(c, notify))
            await waiting.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert len(requests) == 1
        assert notices[0].attempt == 2
        assert notices[-1] is None

    asyncio.run(run())


@pytest.mark.parametrize("streaming", [True, False])
def test_json_error_in_http_200_is_retried(streaming, sleeps):
    async def run():
        response = (
            sse(frame({"content": "ok"}), "[DONE]")
            if streaming
            else httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        )
        responses = [
            httpx.Response(200, json={"error": {"code": 429, "message": "busy"}}),
            response,
        ]
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            result = await collect(c) if streaming else await post_openrouter_json(c, URL, {}, {})
        assert result
        sleeps.assert_awaited_once()

    asyncio.run(run())


def test_non_streaming_retries_share_the_policy(sleeps):
    async def run():
        responses = [httpx.Response(503), httpx.Response(200, json={"choices": []})]
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            assert await post_openrouter_json(c, URL, {}, {}) == {"choices": []}
        sleeps.assert_awaited_once_with(2)

    asyncio.run(run())


@pytest.mark.parametrize("streaming", [True, False])
def test_connect_timeouts_are_retried(streaming, sleeps):
    async def run():
        attempts = 0

        def respond(req):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise httpx.ConnectTimeout("timeout")
            if streaming:
                return sse(frame({"content": "ok"}), "[DONE]")
            return httpx.Response(200, json={"choices": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            if streaming:
                assert await collect(client) == [frame({"content": "ok"}), "[DONE]"]
            else:
                assert await post_openrouter_json(client, URL, {}, {}) == {"choices": []}
        assert attempts == 2
        sleeps.assert_awaited_once()

    asyncio.run(run())


def test_clean_but_truncated_stream_is_a_failure_and_retries_only_before_output(sleeps):
    async def run():
        responses = [sse(frame({"role": "assistant"})), sse(frame({"content": "partial"}))]
        output = []
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: responses.pop(0))
        ) as c:
            with pytest.raises(retry.OpenRouterError, match="ended before"):
                async for data in stream_openrouter_data(c, URL, {}, {}):
                    output.append(data)
        assert output == [frame({"content": "partial"})]
        sleeps.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize(
    "data", ["bad json", json.dumps({"choices": [{"finish_reason": "error"}]})]
)
def test_unknown_stream_errors_are_terminal(data, sleeps):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: sse(data))) as c:
            with pytest.raises(retry.OpenRouterError):
                await collect(c)
        sleeps.assert_not_awaited()

    asyncio.run(run())


def test_sse_preserves_split_unicode_and_multiline_events(sleeps):
    class FragmentedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            encoded = (
                ": heartbeat\r\n\r\n"
                'data: {"choices": [\r\n'
                'data: {"delta": {"content": "héllo 🌍"}, "finish_reason": "stop"}]}\r\n\r\n'
                "data:[DONE]\r\n\r\n"
            ).encode()
            for byte in encoded:
                yield bytes([byte])

    async def run():
        response = httpx.Response(200, stream=FragmentedStream())
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: response)) as c:
            result = await collect(c)
        assert json.loads(result[0])["choices"][0]["delta"]["content"] == "héllo 🌍"
        assert result[-1] == "[DONE]"
        sleeps.assert_not_awaited()

    asyncio.run(run())
