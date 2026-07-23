import asyncio
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_ROOT))

from models.inference import AlibabaTokenPlanApiKeyPayload, InferenceCredentials
from models.message import ToolEnum
from services.alibaba_token_plan import (
    ALIBABA_TOKEN_PLAN_CHAT_URL,
    AlibabaTokenPlanReqChat,
    _parse_alibaba_error,
    make_alibaba_token_plan_request_non_streaming,
    stream_alibaba_token_plan_response,
    validate_alibaba_token_plan_api_key,
)
from services.providers.alibaba_token_plan_catalog import ALIBABA_TOKEN_PLAN_PROVIDER_KEY


async def _stub_current_user_id() -> str:
    return "user-1"


stub_modules = {
    name: ModuleType(name)
    for name in (
        "services.auth",
        "services.claude_agent",
        "services.gemini_cli",
        "services.github_copilot",
        "services.inference",
        "services.openai_codex",
        "services.opencode_go",
        "services.z_ai_coding_plan",
    )
}
stub_modules["services.auth"].get_current_user_id = _stub_current_user_id  # type: ignore[attr-defined]
stub_modules["services.claude_agent"].validate_claude_agent_token = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.gemini_cli"].validate_gemini_cli_oauth_creds_json = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.github_copilot"].validate_github_copilot_token = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.inference"].get_inference_provider_statuses = AsyncMock(  # type: ignore[attr-defined]
    return_value=[]
)
stub_modules["services.inference"].invalidate_user_available_models_cache = MagicMock()  # type: ignore[attr-defined]
stub_modules["services.openai_codex"].complete_openai_codex_device_oauth = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.openai_codex"].start_openai_codex_device_oauth = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.openai_codex"].validate_openai_codex_oauth_auth_json = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.opencode_go"].validate_opencode_go_api_key = AsyncMock()  # type: ignore[attr-defined]
stub_modules["services.z_ai_coding_plan"].validate_z_ai_coding_plan_api_key = AsyncMock()  # type: ignore[attr-defined]
original_modules = {name: sys.modules.get(name) for name in stub_modules}
try:
    sys.modules.update(stub_modules)
    from routers.inference_providers import (
        connect_alibaba_token_plan,
        disconnect_alibaba_token_plan,
    )
finally:
    for module_name, original_module in original_modules.items():
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module


def _config(**overrides: object) -> SimpleNamespace:
    values = {
        "temperature": 1.7,
        "top_p": 0,
        "max_tokens": 256,
        "exclude_reasoning": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides: object) -> AlibabaTokenPlanReqChat:
    values: dict[str, object] = {
        "api_key": "sk-sp-test-key",
        "http_client": AsyncMock(),
        "model": "alibaba-token-plan/future-text-model-v9",
        "model_id": "alibaba-token-plan/future-text-model-v9",
        "messages": [{"role": "user", "content": "Hello"}],
        "config": _config(),
        "user_id": "user-1",
        "pg_engine": MagicMock(),
    }
    values.update(overrides)
    return AlibabaTokenPlanReqChat(**values)


def test_api_key_validation_rejects_prefix_before_outbound_request() -> None:
    client = AsyncMock()

    with pytest.raises(ValueError, match="must start with 'sk-sp-'"):
        asyncio.run(validate_alibaba_token_plan_api_key("sk-wrong", client))

    client.post.assert_not_awaited()


def test_api_key_validation_uses_fixed_probe_and_requires_valid_shape() -> None:
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        json={"choices": [{"message": {"content": "OK"}}]},
    )

    asyncio.run(validate_alibaba_token_plan_api_key("  sk-sp-valid  ", client))

    client.post.assert_awaited_once_with(
        ALIBABA_TOKEN_PLAN_CHAT_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer sk-sp-valid",
        },
        json={
            "model": "qwen3.6-flash",
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "stream": False,
            "max_tokens": 16,
            "enable_thinking": False,
        },
    )

    client.post.return_value = httpx.Response(200, json={"choices": []})
    with pytest.raises(ValueError, match="invalid response"):
        asyncio.run(validate_alibaba_token_plan_api_key("sk-sp-valid", client))


def test_request_payload_normalizes_sampling_reasoning_stream_and_images() -> None:
    image = "data:image/png;base64,secret-image"
    req = _request(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this"},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }
        ]
    )

    req.validate_request()
    payload = req.get_payload()

    assert payload == {
        "model": "future-text-model-v9",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this"},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }
        ],
        "stream": True,
        "temperature": 1.0,
        "top_p": 0.01,
        "max_tokens": 256,
        "enable_thinking": True,
        "stream_options": {"include_usage": True},
    }


@pytest.mark.parametrize(
    "request_overrides, expected",
    [
        ({"schema": SimpleNamespace}, "structured-output"),
        ({"file_uuids": ["file-1"]}, "file or PDF"),
        ({"file_hashes": {"file-1": "hash"}}, "file or PDF"),
        ({"sandbox_input_files": [SimpleNamespace()]}, "file or PDF"),
        (
            {"messages": [{"role": "user", "content": [{"type": "file"}]}]},
            "file or PDF",
        ),
        ({"stream": False, "selected_tools": [ToolEnum.WEB_SEARCH]}, "streaming mode"),
        ({"model": "alibaba-token-plan/"}, "model ID is required"),
        ({"model": "openrouter/future-text-model-v9"}, "model prefix"),
    ],
)
def test_request_validation_rejects_unsupported_modes(
    request_overrides: dict[str, object],
    expected: str,
) -> None:
    req = _request(**request_overrides)

    with pytest.raises(ValueError, match=expected):
        req.validate_request()


def test_title_and_excluded_reasoning_disable_thinking() -> None:
    assert _request(is_title_generation=True).get_payload()["enable_thinking"] is False
    assert (
        _request(config=_config(exclude_reasoning=True)).get_payload()["enable_thinking"] is False
    )


def test_glm_streaming_tools_enable_tool_stream() -> None:
    req = _request(
        model="alibaba-token-plan/GLM-future-chat",
        selected_tools=[ToolEnum.ASK_USER],
    )

    payload = req.get_payload()

    assert payload["tools"]
    assert payload["tool_stream"] is True


def test_non_streaming_parses_content_and_persists_usage() -> None:
    response = httpx.Response(
        200,
        request=httpx.Request("POST", ALIBABA_TOKEN_PLAN_CHAT_URL),
        json={
            "choices": [{"message": {"content": "answer"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
        },
    )
    client = AsyncMock()
    client.post.return_value = response
    req = _request(
        http_client=client,
        stream=False,
        graph_id="graph-1",
        node_id="node-1",
    )

    with patch(
        "services.alibaba_token_plan.update_node_usage_data",
        new=AsyncMock(),
    ) as update_usage:
        result = asyncio.run(make_alibaba_token_plan_request_non_streaming(req, req.pg_engine))

    assert result == "answer"
    update_usage.assert_awaited_once()
    call = client.post.await_args
    assert call.args[0] == ALIBABA_TOKEN_PLAN_CHAT_URL
    assert call.kwargs["headers"]["Authorization"] == "Bearer sk-sp-test-key"
    assert call.kwargs["json"]["stream"] is False
    assert "stream_options" not in call.kwargs["json"]


def test_error_parser_is_bounded_and_redacts_personal_keys() -> None:
    parsed = _parse_alibaba_error(
        b'{"error":{"message":"bad sk-sp-super-secret ' + b"x" * 700 + b'"}}'
    )

    assert "sk-sp-super-secret" not in parsed
    assert "[REDACTED]" in parsed
    assert len(parsed) <= 500


def test_streaming_delegates_to_shared_openai_protocol() -> None:
    req = _request()

    async def fake_stream(*args: object, **kwargs: object):
        assert args[0] is req
        assert kwargs["provider_label"] == "Alibaba Personal Token Plan"
        assert kwargs["preserve_reasoning_content"] is True
        yield "chunk"

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in stream_alibaba_token_plan_response(
                req,
                req.pg_engine,
                MagicMock(),
            )
        ]

    with patch(
        "services.providers.openai_protocol.stream_openai_compatible_response",
        new=fake_stream,
    ):
        chunks = asyncio.run(collect())

    assert chunks == ["chunk"]


def test_request_builder_and_dispatchers_route_alibaba_requests() -> None:
    previous_cwd = Path.cwd()
    try:
        os.chdir(APP_ROOT)
        importlib.import_module("main")
        inference_requests = importlib.import_module("services.inference_requests")
    finally:
        os.chdir(previous_cwd)

    common = {
        "model": "alibaba-token-plan/future-text-model-v9",
        "messages": [{"role": "user", "content": "hello"}],
        "config": _config(),
        "user_id": "user-1",
        "pg_engine": MagicMock(),
        "node_type": "text_to_text",
        "http_client": AsyncMock(),
    }
    with pytest.raises(ValueError, match="not connected"):
        inference_requests.build_inference_request(
            credentials=InferenceCredentials(),
            **common,
        )

    req = inference_requests.build_inference_request(
        credentials=InferenceCredentials(alibaba_token_plan_api_key="sk-sp-valid"),
        stream=False,
        **common,
    )
    assert isinstance(req, AlibabaTokenPlanReqChat)

    with patch.object(
        inference_requests,
        "make_alibaba_token_plan_request_non_streaming",
        new=AsyncMock(return_value="answer"),
    ) as non_stream:
        result = asyncio.run(
            inference_requests.make_inference_request_non_streaming(req, req.pg_engine)
        )
    assert result == "answer"
    non_stream.assert_awaited_once()

    async def fake_stream(*args: object, **kwargs: object):
        yield "streamed"

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in inference_requests.stream_inference_response(
                req,
                req.pg_engine,
                MagicMock(),
            )
        ]

    with patch.object(
        inference_requests,
        "stream_alibaba_token_plan_response",
        new=fake_stream,
    ):
        assert asyncio.run(collect()) == ["streamed"]


def test_connect_route_validates_encrypts_stores_then_invalidates() -> None:
    events: list[str] = []
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(pg_engine=MagicMock(), http_client=AsyncMock()))
    )

    async def validate(*args: object, **kwargs: object) -> None:
        events.append("validate")

    async def encrypt(value: str) -> str:
        assert value == "sk-sp-valid"
        events.append("encrypt")
        return "encrypted"

    async def store(*args: object) -> None:
        assert args[2:] == (ALIBABA_TOKEN_PLAN_PROVIDER_KEY, "encrypted")
        events.append("store")

    def invalidate(*args: object) -> None:
        events.append("invalidate")

    with (
        patch("routers.inference_providers.validate_alibaba_token_plan_api_key", new=validate),
        patch("routers.inference_providers.encrypt_api_key", new=encrypt),
        patch("routers.inference_providers.store_provider_token", new=store),
        patch("routers.inference_providers.invalidate_user_available_models_cache", new=invalidate),
    ):
        result = asyncio.run(
            connect_alibaba_token_plan(
                request,
                AlibabaTokenPlanApiKeyPayload(api_key="  sk-sp-valid  "),
                "user-1",
            )
        )

    assert result == {"message": "Alibaba Personal Token Plan connected successfully."}
    assert events == ["validate", "encrypt", "store", "invalidate"]


def test_connect_route_does_not_store_failed_validation() -> None:
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(pg_engine=MagicMock(), http_client=AsyncMock()))
    )
    store = AsyncMock()
    with (
        patch(
            "routers.inference_providers.validate_alibaba_token_plan_api_key",
            new=AsyncMock(side_effect=ValueError("invalid key")),
        ),
        patch("routers.inference_providers.store_provider_token", new=store),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                connect_alibaba_token_plan(
                    request,
                    AlibabaTokenPlanApiKeyPayload(api_key="sk-sp-invalid"),
                    "user-1",
                )
            )

    assert exc_info.value.status_code == 400
    store.assert_not_awaited()


def test_disconnect_route_deletes_token_and_invalidates_cache() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine=MagicMock())))
    delete = AsyncMock()
    invalidate = MagicMock()
    with (
        patch("routers.inference_providers.delete_provider_token", new=delete),
        patch(
            "routers.inference_providers.invalidate_user_available_models_cache",
            new=invalidate,
        ),
    ):
        result = asyncio.run(disconnect_alibaba_token_plan(request, "user-1"))

    delete.assert_awaited_once_with(
        request.app.state.pg_engine,
        "user-1",
        ALIBABA_TOKEN_PLAN_PROVIDER_KEY,
    )
    invalidate.assert_called_once_with(request.app, "user-1")
    assert result == {"message": "Alibaba Personal Token Plan disconnected successfully."}
