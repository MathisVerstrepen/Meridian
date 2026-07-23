import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from services.web.browser_fetch import BrowserFetchManager
from services.web.fetch_errors import BrowserFetchError, LinkExtractionFailureReason

TOKEN = "a" * 64
URL = "http://browser_service:5010"


def manager_for(handler):
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    env = {
        "LINK_EXTRACTION_BROWSER_SERVICE_URL": URL,
        "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN": TOKEN,
    }
    return BrowserFetchManager(client_factory=factory, env_getter=env.get), calls


def test_success_is_authenticated_lazy_http1_and_no_retry() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"request_id": body["request_id"], "html": "<html>ok</html>"},
        )

    manager, factory_calls = manager_for(handler)

    async def scenario() -> str:
        result = await manager.fetch("https://example.com/private?token=secret")
        await manager.close()
        await manager.close()
        return result

    assert asyncio.run(scenario()) == "<html>ok</html>"
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert requests[0].url == f"{URL}/v1/fetch"
    assert factory_calls[0]["http2"] is False
    assert factory_calls[0]["trust_env"] is False


@pytest.mark.parametrize(
    ("reason", "status_code"),
    [
        (reason, 403 if reason is LinkExtractionFailureReason.HTTP_REJECTED else None)
        for reason in LinkExtractionFailureReason
    ],
)
def test_typed_failures_are_preserved(
    reason: LinkExtractionFailureReason, status_code: int | None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        request_id = json.loads(request.content)["request_id"]
        return httpx.Response(
            502,
            headers={"content-type": "application/json"},
            json={
                "request_id": request_id,
                "error": {"reason": reason.value, "status_code": status_code},
            },
        )

    manager, _ = manager_for(handler)
    with pytest.raises(BrowserFetchError) as captured:
        asyncio.run(manager.fetch("https://example.com"))
    assert captured.value.reason is reason
    assert captured.value.status_code == status_code


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"detail": "unauthorized"}),
        httpx.Response(200, text="not-json", headers={"content-type": "text/plain"}),
        httpx.Response(
            200,
            json={"request_id": "wrong", "html": "secret"},
            headers={"content-type": "application/json"},
        ),
        httpx.Response(
            502,
            json={
                "request_id": "wrong",
                "error": {"reason": "raw", "status_code": 999},
            },
            headers={"content-type": "application/json"},
        ),
    ],
)
def test_auth_and_malformed_responses_map_to_browser_failed(
    response: httpx.Response,
) -> None:
    manager, _ = manager_for(lambda request: response)
    with pytest.raises(BrowserFetchError) as captured:
        asyncio.run(manager.fetch("https://example.com"))
    assert captured.value.reason is LinkExtractionFailureReason.BROWSER_FAILED


def test_transport_timeout_maps_to_connectivity_without_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("raw secret", request=request)

    manager, _ = manager_for(handler)
    with pytest.raises(BrowserFetchError) as captured:
        asyncio.run(manager.fetch("https://example.com"))
    assert captured.value.reason is LinkExtractionFailureReason.CONNECTIVITY_EXHAUSTED
    assert calls == 1


def test_concurrent_calls_use_independent_request_ids() -> None:
    request_ids = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        request_ids.append(body["request_id"])
        await asyncio.sleep(0)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"request_id": body["request_id"], "html": body["url"]},
        )

    manager, _ = manager_for(handler)

    async def scenario() -> list[str]:
        results = await asyncio.gather(
            manager.fetch("https://example.com/one"),
            manager.fetch("https://example.com/two"),
        )
        await manager.close()
        return results

    assert asyncio.run(scenario()) == [
        "https://example.com/one",
        "https://example.com/two",
    ]
    assert len(set(request_ids)) == 2


def test_close_cancels_owned_operation_without_waiting_for_caller_cleanup() -> None:
    started = asyncio.Event()
    child_cancelled = asyncio.Event()
    caller_caught = asyncio.Event()
    finish_caller = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            child_cancelled.set()

    manager, _ = manager_for(handler)

    async def scenario() -> None:
        async def caller() -> None:
            try:
                await manager.fetch("https://example.com")
            except asyncio.CancelledError:
                caller_caught.set()
                await finish_caller.wait()

        pending = asyncio.create_task(caller())
        await started.wait()
        await asyncio.wait_for(manager.close(), timeout=1)
        assert child_cancelled.is_set() and caller_caught.is_set()
        assert not pending.done()
        finish_caller.set()
        await pending
        with pytest.raises(BrowserFetchError):
            await manager.fetch("https://example.com")

    asyncio.run(scenario())


def test_caller_cancellation_drains_owned_operation() -> None:
    started = asyncio.Event()
    child_cancelled = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            child_cancelled.set()

    manager, _ = manager_for(handler)

    async def scenario() -> None:
        caller = asyncio.create_task(manager.fetch("https://example.com"))
        await started.wait()
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert child_cancelled.is_set()
        assert not manager._in_flight
        await manager.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("url", "token"),
    [
        ("", TOKEN),
        ("ftp://browser", TOKEN),
        (URL, "short"),
        ("http://user:pass@browser", TOKEN),
    ],
)
def test_invalid_lazy_configuration_is_typed(url: str, token: str) -> None:
    env = {
        "LINK_EXTRACTION_BROWSER_SERVICE_URL": url,
        "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN": token,
    }
    manager = BrowserFetchManager(env_getter=env.get)
    with pytest.raises(BrowserFetchError):
        asyncio.run(manager.fetch("https://example.com"))


@pytest.mark.parametrize(
    "token",
    [
        "x" * 31,
        " " + "x" * 32,
        "x" * 32 + " ",
        "x" * 16 + " " + "x" * 16,
        "x" * 16 + "\t" + "x" * 16,
        "x" * 16 + "\r" + "x" * 16,
        "x" * 16 + "\n" + "x" * 16,
        "x" * 32 + "\x7f",
        "x" * 32 + "\x1f",
        "é" * 32,
        "🦊" * 8,
        "",
        "change-me",
        "replace-me",
        "example",
    ],
)
def test_invalid_header_tokens_fail_before_client_creation(token: str) -> None:
    factory_calls = []
    env = {
        "LINK_EXTRACTION_BROWSER_SERVICE_URL": URL,
        "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN": token,
    }
    manager = BrowserFetchManager(
        client_factory=lambda **kwargs: factory_calls.append(kwargs), env_getter=env.get
    )
    with pytest.raises(BrowserFetchError):
        asyncio.run(manager.fetch("https://example.com"))
    assert factory_calls == []


@pytest.mark.parametrize("token", ["!" * 32, "0123456789abcdef" * 4])
def test_visible_ascii_tokens_are_valid(token: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        request_id = json.loads(request.content)["request_id"]
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"request_id": request_id, "html": "ok"},
        )

    env = {
        "LINK_EXTRACTION_BROWSER_SERVICE_URL": URL,
        "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN": token,
    }

    def factory(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)

    manager = BrowserFetchManager(client_factory=factory, env_getter=env.get)
    assert asyncio.run(manager.fetch("https://example.com")) == "ok"


def test_environment_proxies_are_bypassed(monkeypatch) -> None:
    async def scenario() -> tuple[int, int]:
        sidecar_requests = 0
        proxy_requests = 0

        async def sidecar(reader, writer) -> None:
            nonlocal sidecar_requests
            headers = await reader.readuntil(b"\r\n\r\n")
            content_length = 0
            for line in headers.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    content_length = int(line.split(b":", 1)[1])
            body = json.loads(await reader.readexactly(content_length))
            sidecar_requests += 1
            payload = json.dumps({"request_id": body["request_id"], "html": "ok"}).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(payload)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + payload
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        async def proxy(reader, writer) -> None:
            nonlocal proxy_requests
            proxy_requests += 1
            writer.close()
            await writer.wait_closed()

        sidecar_server = await asyncio.start_server(sidecar, "127.0.0.1", 0)
        proxy_server = await asyncio.start_server(proxy, "127.0.0.1", 0)
        sidecar_port = sidecar_server.sockets[0].getsockname()[1]
        proxy_port = proxy_server.sockets[0].getsockname()[1]
        proxy_url = f"http://127.0.0.1:{proxy_port}"
        for name in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            monkeypatch.setenv(name, proxy_url)
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("no_proxy", "")
        env = {
            "LINK_EXTRACTION_BROWSER_SERVICE_URL": f"http://127.0.0.1:{sidecar_port}",
            "LINK_EXTRACTION_BROWSER_SERVICE_TOKEN": TOKEN,
        }
        manager = BrowserFetchManager(env_getter=env.get)
        try:
            assert await manager.fetch("https://example.com/private") == "ok"
        finally:
            await manager.close()
            sidecar_server.close()
            proxy_server.close()
            await sidecar_server.wait_closed()
            await proxy_server.wait_closed()
        return sidecar_requests, proxy_requests

    assert asyncio.run(scenario()) == (1, 0)
