import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

from services.providers.opencode_go_validation import validate_opencode_go_api_key  # noqa: E402


def test_validation_uses_current_subscription_model_and_matching_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == "https://opencode.ai/inference/go/openai/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["User-Agent"] == "Meridian/1.0"
        assert request.headers["x-opencode-session"]
        assert json.loads(request.content) == {
            "model": "kimi-k3",
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "stream": False,
            "max_tokens": 16,
        }
        return httpx.Response(200, json={"choices": []})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await validate_opencode_go_api_key("test-key", http_client=client)

    asyncio.run(run())
    assert len(requests) == 1


@pytest.mark.parametrize("status", [400, 404])
@pytest.mark.parametrize("unavailable_count", [1, 2])
def test_validation_falls_back_only_when_a_probe_model_is_unavailable(
    status: int, unavailable_count: int
) -> None:
    models: list[str] = []
    sessions: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        models.append(json.loads(request.content)["model"])
        sessions.append(request.headers["x-opencode-session"])
        if len(models) <= unavailable_count:
            return httpx.Response(
                status,
                json={"error": {"message": "Upstream request failed: Model is unavailable."}},
            )
        return httpx.Response(200, json={"choices": []})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await validate_opencode_go_api_key("test-key", http_client=client)

    asyncio.run(run())
    assert models == ["kimi-k3", "glm-5.3-flash", "deepseek-v4.1-flash"][: unavailable_count + 1]
    assert len(set(sessions)) == 1


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (400, "Request is missing x-opencode-session"),
        (401, "Invalid API key"),
        (403, "Subscription required"),
        (429, "Rate limit exceeded"),
        (500, "Internal server error"),
        (401, "Model is unavailable"),
    ],
)
def test_validation_stops_on_authentication_and_other_errors(status: int, message: str) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": message}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError, match=rf"status {status}.*{message}"):
                await validate_opencode_go_api_key("test-key", http_client=client)

    asyncio.run(run())
    assert len(requests) == 1


def test_validation_rejects_when_all_probe_models_are_unavailable() -> None:
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        models.append(json.loads(request.content)["model"])
        return httpx.Response(400, json={"error": {"message": "Model is unavailable."}})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError, match="validation is temporarily unavailable"):
                await validate_opencode_go_api_key("test-key", http_client=client)

    asyncio.run(run())
    assert models == ["kimi-k3", "glm-5.3-flash", "deepseek-v4.1-flash"]
