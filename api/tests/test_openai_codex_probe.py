import asyncio
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))
importlib.import_module("services.graph_service")

from services.openai_codex import _probe_openai_codex_auth  # noqa: E402

AUTH_JSON = json.dumps({"tokens": {"access_token": "test-access", "account_id": "account-1"}})


class _EventStream(httpx.AsyncByteStream):
    def __init__(self, events: list[dict[str, object]]) -> None:
        self.events = events

    async def __aiter__(self):
        for event in self.events:
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()


def _stream_response(*events: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, stream=_EventStream(list(events)))


def _run_probe(
    handler: Callable[[httpx.Request], httpx.Response], auth_json: str = AUTH_JSON
) -> None:
    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch("services.openai_codex.httpx.AsyncClient", return_value=client):
            await _probe_openai_codex_auth(auth_json)

    asyncio.run(run())


def test_probe_uses_current_model_and_preserves_codex_oauth_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == "https://chatgpt.com/backend-api/codex/responses"
        assert request.headers["Authorization"] == "Bearer test-access"
        assert request.headers["ChatGPT-Account-Id"] == "account-1"
        assert request.headers["session-id"]
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-6-luna"
        assert payload["instructions"]
        assert payload["stream"] is True
        assert payload["store"] is False
        assert "max_output_tokens" not in payload
        return _stream_response({"type": "response.completed"})

    _run_probe(handler)
    assert len(requests) == 1


@pytest.mark.parametrize("unsupported_count", [1, 2])
def test_unsupported_account_model_tries_a_current_alternative(unsupported_count: int) -> None:
    models: list[str] = []
    sessions: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        models.append(model)
        sessions.append(request.headers["session-id"])
        if len(models) <= unsupported_count:
            return httpx.Response(
                400,
                json={
                    "detail": f"The '{model}' model is not supported when using Codex "
                    "with a ChatGPT account."
                },
            )
        return _stream_response({"type": "response.completed"})

    _run_probe(handler)
    assert models == ["gpt-6-luna", "gpt-6.1-sol", "gpt-6-sol"][: unsupported_count + 1]
    assert len(set(sessions)) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_non_model_failures_stop_immediately_and_only_401_requests_sign_in(status: int) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"detail": "Upstream rejection"})

    with pytest.raises(ValueError) as error:
        _run_probe(handler)

    assert len(requests) == 1
    assert f"({status}" in str(error.value)
    assert ("Sign in again" in str(error.value)) is (status == 401)


def test_no_available_model_is_reported_as_model_access_failure() -> None:
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        models.append(json.loads(request.content)["model"])
        return httpx.Response(400, json={"detail": "This model is not supported."})

    with pytest.raises(ValueError, match="none of the validation models is available") as error:
        _run_probe(handler)

    assert models == ["gpt-6-luna", "gpt-6.1-sol", "gpt-6-sol"]
    assert "Sign in again" not in str(error.value)
    assert "authentication is invalid" not in str(error.value)


def test_error_after_response_created_is_not_accepted_as_valid_authentication() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _stream_response(
            {"type": "response.created"},
            {"type": "response.failed", "response": {"error": {"message": "Quota exceeded"}}},
        )

    with pytest.raises(ValueError, match="Quota exceeded"):
        _run_probe(handler)


def test_streaming_model_rejection_uses_the_same_fallback_as_http_rejection() -> None:
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        models.append(json.loads(request.content)["model"])
        if len(models) == 1:
            return _stream_response(
                {"type": "response.created"},
                {"type": "error", "message": "This model is not supported."},
            )
        return _stream_response({"type": "response.completed"})

    _run_probe(handler)
    assert models == ["gpt-6-luna", "gpt-6.1-sol"]


@pytest.mark.parametrize("events", [[], [{"type": "response.created"}]])
def test_truncated_validation_stream_is_rejected(events: list[dict[str, object]]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _stream_response(*events)

    with pytest.raises(ValueError, match="without a completed response"):
        _run_probe(handler)


def test_api_key_validation_uses_models_endpoint_without_a_chatgpt_probe() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert str(request.url) == "https://api.openai.com/v1/models"
        assert request.headers["Authorization"] == "Bearer sk-test"
        return httpx.Response(200, json={"data": []})

    _run_probe(handler, json.dumps({"OPENAI_API_KEY": "sk-test"}))
    assert len(requests) == 1
