import asyncio
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from models.message import ToolEnum
from models.tool_question import AskUserArguments
from services.github_copilot import (
    GitHubCopilotReqChat,
    _build_copilot_system_message,
    _clear_github_copilot_model_cache,
    _format_model_unavailable_error,
    _is_model_unavailable_error,
    _list_sdk_models,
    _public_github_copilot_stream_error_message,
    list_github_copilot_models,
    make_github_copilot_request_non_streaming,
    stream_github_copilot_response,
)
from services.inference import (
    CLAUDE_AGENT_SUPPORTED_TOOL_NAMES,
    GEMINI_CLI_SUPPORTED_TOOL_NAMES,
    GITHUB_COPILOT_SUPPORTED_TOOL_NAMES,
    OPENAI_CODEX_SUPPORTED_TOOL_NAMES,
    OPENCODE_GO_SUPPORTED_TOOL_NAMES,
    Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES,
    get_github_copilot_models_safe,
    get_openai_codex_models_safe,
    get_supported_meridian_tool_names,
    model_supports_structured_outputs,
    normalize_openrouter_model,
    resolve_model_provider,
)
from services.openai_codex import (
    OpenAICodexReqChat,
    _build_codex_auth_json_from_tokens,
    _build_dynamic_tools,
    _build_openai_codex_direct_headers,
    _build_openai_codex_direct_image_input,
    _build_openai_codex_direct_image_payload,
    _build_openai_codex_direct_input,
    _build_openai_codex_direct_payload,
    _build_pending_assistant_message,
    _codex_auth_needs_refresh,
    _extract_account_id_from_claims,
    _extract_openai_codex_direct_image_result,
    _extract_reasoning_item_text,
    _extract_system_instructions,
    _iter_openai_codex_sse_events,
    _normalize_auth_json,
    _normalize_codex_usage_data,
    _normalize_openai_responses_usage_data,
    _OpenAICodexDirectTurnRunner,
    _openai_codex_device_sessions,
    _probe_openai_codex_auth,
    _sanitize_model_instructions,
    complete_openai_codex_device_oauth,
    generate_image_with_openai_codex,
    list_openai_codex_models,
    make_openai_codex_request_non_streaming,
    start_openai_codex_device_oauth,
    validate_openai_codex_oauth_auth_json,
)
from services.providers.claude_agent_catalog import CLAUDE_AGENT_MODELS, get_claude_agent_models
from services.providers.common import sanitize_external_tool_references
from services.providers.gemini_cli_bridge_utils import extract_bridge_json_payload
from services.providers.gemini_cli_catalog import GEMINI_CLI_MODELS, get_gemini_cli_models
from services.providers.github_copilot_catalog import normalize_github_copilot_model
from services.providers.models_dev import reduce_models_dev_catalog
from services.providers.openai_codex_catalog import (
    build_openai_codex_models_from_models_dev,
    normalize_openai_codex_model,
)
from services.providers.opencode_go_catalog import (
    OPENCODE_GO_TEMPERATURE_OVERRIDES,
    OPENCODE_GO_TOP_P_OVERRIDES,
    build_opencode_go_models_from_models_dev,
    get_opencode_go_models,
)
from services.providers.z_ai_coding_plan_catalog import (
    build_z_ai_coding_plan_models_from_models_dev,
    get_z_ai_coding_plan_models,
)


def test_resolve_model_provider_uses_prefix_for_claude_agent():
    assert resolve_model_provider("claude-agent/sonnet") == InferenceProviderEnum.CLAUDE_AGENT
    assert resolve_model_provider("z-ai-plan/glm-5.1") == InferenceProviderEnum.Z_AI_CODING_PLAN
    assert resolve_model_provider("github-copilot/gpt-5") == InferenceProviderEnum.GITHUB_COPILOT
    assert resolve_model_provider("gemini-cli/flash") == InferenceProviderEnum.GEMINI_CLI
    assert resolve_model_provider("openai-codex/gpt-5.4") == InferenceProviderEnum.OPENAI_CODEX
    assert resolve_model_provider("openai/gpt-5.4-mini") == InferenceProviderEnum.OPENROUTER


def test_claude_agent_catalog_is_subscription_only_and_not_structured():
    assert CLAUDE_AGENT_MODELS
    for model in CLAUDE_AGENT_MODELS:
        assert model.provider == InferenceProviderEnum.CLAUDE_AGENT
        assert model.billingType == BillingTypeEnum.SUBSCRIPTION
        assert model.supportsStructuredOutputs is False
        assert model.supportsMeridianTools is True
        assert model.supportedMeridianToolNames == CLAUDE_AGENT_SUPPORTED_TOOL_NAMES


def test_z_ai_coding_plan_catalog_is_subscription_only_and_not_structured():
    models = build_z_ai_coding_plan_models_from_models_dev(
        {
            "zai-coding-plan": {
                "models": {
                    "glm-5.2": {
                        "id": "glm-5.2",
                        "name": "GLM-5.2",
                        "release_date": "2026-06-13",
                        "modalities": {"input": ["text"], "output": ["text"]},
                        "limit": {"context": 1000000},
                        "cost": {"input": 0, "output": 0},
                    }
                }
            }
        }
    )

    assert models
    for model in models:
        assert model.provider == InferenceProviderEnum.Z_AI_CODING_PLAN
        assert model.billingType == BillingTypeEnum.SUBSCRIPTION
        assert model.supportsStructuredOutputs is False
        assert model.supportsMeridianTools is True
        assert model.supportedMeridianToolNames == Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES


def test_z_ai_coding_plan_models_dev_catalog_filters_to_text_models():
    models = build_z_ai_coding_plan_models_from_models_dev(
        {
            "zai-coding-plan": {
                "models": {
                    "glm-5.2": {
                        "id": "glm-5.2",
                        "name": "GLM-5.2",
                        "release_date": "2026-06-13",
                        "modalities": {"input": ["text"], "output": ["text"]},
                        "limit": {"context": 1000000},
                        "cost": {"input": 0, "output": 0},
                    },
                    "glm-5v-turbo": {
                        "id": "glm-5v-turbo",
                        "name": "GLM-5V-Turbo",
                        "release_date": "2026-04-01",
                        "modalities": {"input": ["text", "image"], "output": ["text"]},
                        "limit": {"context": 200000},
                    },
                }
            }
        }
    )

    assert [model.id for model in models] == ["z-ai-plan/glm-5.2"]
    assert models[0].context_length == 1000000
    assert models[0].created == "2026-06-13"
    assert models[0].pricing.prompt == "0"
    assert models[0].pricing.completion == "0"
    assert models[0].supportsStructuredOutputs is False


def test_opencode_go_catalog_is_subscription_only_and_not_structured():
    models = build_opencode_go_models_from_models_dev(
        {
            "opencode-go": {
                "models": {
                    "kimi-k2.7-code": {
                        "id": "kimi-k2.7-code",
                        "name": "Kimi K2.7 Code",
                        "release_date": "2026-06-12",
                        "modalities": {"input": ["text", "image", "video"], "output": ["text"]},
                        "limit": {"context": 262144},
                        "cost": {"input": 0.95, "output": 4},
                    }
                }
            }
        }
    )

    assert models
    for model in models:
        assert model.provider == InferenceProviderEnum.OPENCODE_GO
        assert model.billingType == BillingTypeEnum.SUBSCRIPTION
        assert model.supportsStructuredOutputs is False
        assert model.supportsMeridianTools is True
        assert model.supportedMeridianToolNames == OPENCODE_GO_SUPPORTED_TOOL_NAMES


def test_opencode_go_models_dev_catalog_normalizes_metadata():
    models = build_opencode_go_models_from_models_dev(
        {
            "opencode-go": {
                "models": {
                    "glm-5": {
                        "id": "glm-5",
                        "name": "GLM-5",
                        "release_date": "2026-04-01",
                        "modalities": {"input": ["text"], "output": ["text"]},
                        "limit": {"context": 202752},
                        "cost": {"input": 1.4, "output": 4.4},
                    },
                    "qwen3.7-plus": {
                        "id": "qwen3.7-plus",
                        "name": "Qwen3.7 Plus",
                        "release_date": "2026-06-02",
                        "modalities": {"input": ["text", "image", "video"], "output": ["text"]},
                        "limit": {"context": 1000000},
                        "cost": {"input": 0.4, "output": 1.6},
                    },
                }
            }
        }
    )

    assert [model.id for model in models] == ["opencode-go/qwen3.7-plus", "opencode-go/glm-5"]
    assert models[0].architecture.input_modalities == ["text", "image", "video"]
    assert models[0].architecture.modality == "text+image+video->text"
    assert models[0].context_length == 1000000
    assert models[0].created == "2026-06-02"
    assert models[0].pricing.prompt == "0.4"
    assert models[0].pricing.completion == "1.6"


def test_gemini_cli_catalog_is_subscription_only_and_structured():
    assert GEMINI_CLI_MODELS
    for model in GEMINI_CLI_MODELS:
        assert model.provider == InferenceProviderEnum.GEMINI_CLI
        assert model.billingType == BillingTypeEnum.SUBSCRIPTION
        assert model.supportsStructuredOutputs is True
        assert model.supportsMeridianTools is True
        assert model.supportedMeridianToolNames == GEMINI_CLI_SUPPORTED_TOOL_NAMES


def test_normalize_openai_codex_model_marks_subscription_and_structure_support():
    normalized = normalize_openai_codex_model(
        {
            "id": "gpt-5.4",
            "displayName": "GPT-5.4",
            "inputModalities": ["text", "image"],
            "defaultReasoningEffort": "medium",
        }
    )

    assert normalized is not None
    assert normalized.id == "openai-codex/gpt-5.4"
    assert normalized.provider == InferenceProviderEnum.OPENAI_CODEX
    assert normalized.billingType == BillingTypeEnum.SUBSCRIPTION
    assert normalized.supportsStructuredOutputs is True
    assert normalized.supportsMeridianTools is True
    assert normalized.supportedMeridianToolNames == OPENAI_CODEX_SUPPORTED_TOOL_NAMES
    assert normalized.architecture.input_modalities == ["text", "image"]
    assert normalized.architecture.modality == "text + image->text"


def test_normalize_openai_codex_model_accepts_gpt_5_5():
    normalized = normalize_openai_codex_model(
        {
            "id": "gpt-5.5",
            "inputModalities": ["text", "image"],
            "defaultReasoningEffort": "medium",
            "contextLength": 400000,
        }
    )

    assert normalized is not None
    assert normalized.id == "openai-codex/gpt-5.5"
    assert normalized.name == "GPT-5.5"
    assert normalized.context_length == 400000
    assert normalized.provider == InferenceProviderEnum.OPENAI_CODEX
    assert normalized.architecture.modality == "text + image->text"


def test_normalize_github_copilot_model_marks_subscription_and_tools():
    raw_model = SimpleNamespace(
        id="gpt-5",
        name="GPT-5",
        capabilities=SimpleNamespace(
            supports=SimpleNamespace(vision=True),
            limits=SimpleNamespace(max_context_window_tokens=200000),
        ),
    )

    normalized = normalize_github_copilot_model(raw_model)

    assert normalized is not None
    assert normalized.id == "github-copilot/gpt-5"
    assert normalized.provider == InferenceProviderEnum.GITHUB_COPILOT
    assert normalized.billingType == BillingTypeEnum.SUBSCRIPTION
    assert normalized.supportsStructuredOutputs is False
    assert normalized.supportsMeridianTools is True
    assert normalized.supportedMeridianToolNames == GITHUB_COPILOT_SUPPORTED_TOOL_NAMES
    assert normalized.architecture.input_modalities == ["text"]
    assert normalized.architecture.modality == "text->text"


def test_normalize_github_copilot_model_accepts_raw_dict_without_billing_multiplier():
    normalized = normalize_github_copilot_model(
        {
            "id": "gpt-5-mini",
            "name": "GPT-5 Mini",
            "capabilities": {
                "supports": {"vision": False},
                "limits": {"max_context_window_tokens": 128000},
            },
            "billing": {},
        }
    )

    assert normalized is not None
    assert normalized.id == "github-copilot/gpt-5-mini"
    assert normalized.name == "GPT-5 Mini"
    assert normalized.context_length == 128000


def test_normalize_openrouter_model_sets_provider_capabilities():
    raw_model = ModelInfo(
        id="openai/gpt-4o-mini",
        name="GPT-4o mini",
        icon="openai",
        architecture=Architecture(
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="gpt",
        ),
        pricing=Pricing(prompt="0.1", completion="0.2"),
        toolsSupport=True,
    )

    normalized = normalize_openrouter_model(raw_model)

    assert normalized.provider == InferenceProviderEnum.OPENROUTER
    assert normalized.billingType == BillingTypeEnum.METERED
    assert normalized.supportsStructuredOutputs is True
    assert normalized.supportsMeridianTools is True
    assert "ask_user" in normalized.supportedMeridianToolNames


def test_reduce_models_dev_catalog_keeps_only_used_providers_and_models():
    reduced = reduce_models_dev_catalog(
        {
            "openai": {"api": "unused", "models": {"gpt-5.5": {"name": "GPT-5.5"}}},
            "zai-coding-plan": {
                "doc": "unused",
                "models": {"glm-5.2": {"name": "GLM-5.2"}},
            },
            "opencode-go": {
                "api": "unused",
                "models": {"glm-5": {"name": "GLM-5"}},
            },
            "anthropic": {"models": {"claude-sonnet-4-6": {"name": "Claude"}}},
        }
    )

    assert set(reduced) == {"openai", "zai-coding-plan", "opencode-go"}
    assert reduced["openai"] == {"models": {"gpt-5.5": {"name": "GPT-5.5"}}}
    assert reduced["zai-coding-plan"] == {"models": {"glm-5.2": {"name": "GLM-5.2"}}}
    assert reduced["opencode-go"] == {"models": {"glm-5": {"name": "GLM-5"}}}


def test_model_supports_structured_outputs_reads_dict_and_model_instances():
    assert (
        model_supports_structured_outputs(
            "claude-agent/sonnet",
            [model.model_dump(mode="json") for model in CLAUDE_AGENT_MODELS],
        )
        is False
    )
    assert model_supports_structured_outputs("claude-agent/sonnet", CLAUDE_AGENT_MODELS) is False


def test_opencode_go_sampling_overrides_for_fixed_sampling_model():
    assert OPENCODE_GO_TEMPERATURE_OVERRIDES["kimi-k2.7-code"] == 1.0
    assert OPENCODE_GO_TOP_P_OVERRIDES["kimi-k2.7-code"] == 0.95


def test_supported_meridian_tools_are_provider_specific():
    assert (
        get_supported_meridian_tool_names("claude-agent/sonnet")
        == CLAUDE_AGENT_SUPPORTED_TOOL_NAMES
    )
    assert (
        get_supported_meridian_tool_names("z-ai-plan/glm-5.1")
        == Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES
    )
    assert (
        get_supported_meridian_tool_names("github-copilot/gpt-5")
        == GITHUB_COPILOT_SUPPORTED_TOOL_NAMES
    )
    assert get_supported_meridian_tool_names("gemini-cli/flash") == GEMINI_CLI_SUPPORTED_TOOL_NAMES
    assert (
        get_supported_meridian_tool_names("openai-codex/gpt-5.4")
        == OPENAI_CODEX_SUPPORTED_TOOL_NAMES
    )
    assert "ask_user" in get_supported_meridian_tool_names("openai/gpt-4o-mini")


def test_normalize_openai_codex_auth_json_sorts_keys():
    assert _normalize_auth_json('{"b":2,"a":1}') == '{"a":1,"b":2}'


def test_normalize_openai_codex_auth_json_accepts_non_breaking_spaces():
    assert _normalize_auth_json('{\u00a0"b":2,\u00a0"a":1\u00a0}') == '{"a":1,"b":2}'


def _unsigned_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("ascii").rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{header}.{body}.sig"


def test_openai_codex_extract_account_id_prefers_auth_namespace():
    assert (
        _extract_account_id_from_claims(
            {"https://api.openai.com/auth": {"chatgpt_account_id": "acc-nested"}}
        )
        == "acc-nested"
    )


def test_build_openai_codex_auth_json_from_oauth_tokens_uses_codex_shape():
    id_token = _unsigned_jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acc-123"}})
    auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": id_token,
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }
    )

    payload = json.loads(auth_json)
    assert payload["auth_mode"] == "chatgpt"
    assert payload["OPENAI_API_KEY"] is None
    assert payload["tokens"]["id_token"] == id_token
    assert payload["tokens"]["access_token"]
    assert payload["tokens"]["refresh_token"] == "refresh-token"
    assert payload["tokens"]["account_id"] == "acc-123"


def test_openai_codex_auth_refresh_check_uses_access_token_expiration():
    expired_auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 1}),
            "refresh_token": "refresh-token",
        }
    )
    fresh_auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }
    )

    assert _codex_auth_needs_refresh(expired_auth_json)
    assert not _codex_auth_needs_refresh(fresh_auth_json)


def _openai_codex_test_req(auth_json: str | None = None) -> OpenAICodexReqChat:
    if auth_json is None:
        auth_json = _build_codex_auth_json_from_tokens(
            {
                "id_token": _unsigned_jwt(
                    {"https://api.openai.com/auth": {"chatgpt_account_id": "acc-123"}}
                ),
                "access_token": _unsigned_jwt({"exp": 4102444800}),
                "refresh_token": "refresh-token",
            }
        )
    return OpenAICodexReqChat(
        auth_json=auth_json,
        model="openai-codex/gpt-5.5",
        model_id="openai-codex/gpt-5.5",
        messages=[
            {"role": "system", "content": "Follow the rules."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this."},
                    {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}},
                ],
            },
        ],
        config=SimpleNamespace(exclude_reasoning=False, reasoning_effort="low"),
        user_id="user-1",
        graph_id="graph-1",
        node_id="node-1",
        pg_engine=None,
    )


def test_openai_codex_direct_headers_use_chatgpt_codex_endpoint_and_account_id():
    req = _openai_codex_test_req()
    endpoint, headers = _build_openai_codex_direct_headers(req.auth_json, req=req)

    assert endpoint == "https://chatgpt.com/backend-api/codex/responses"
    assert headers["Authorization"].startswith("Bearer ")
    assert headers["ChatGPT-Account-Id"] == "acc-123"
    assert headers["originator"] == "meridian"
    assert headers["session-id"] == "graph-1"


def test_openai_codex_direct_payload_matches_responses_shape():
    req = _openai_codex_test_req()
    input_items = _build_openai_codex_direct_input(req)
    payload = _build_openai_codex_direct_payload(req, input_items)

    assert payload["model"] == "gpt-5.5"
    assert payload["instructions"] == "Follow the rules."
    assert payload["tool_choice"] == "auto"
    assert payload["parallel_tool_calls"] is False
    assert payload["store"] is False
    assert payload["stream"] is True
    assert payload["reasoning"] == {"effort": "low", "summary": "auto"}
    assert payload["include"] == ["reasoning.encrypted_content"]
    assert payload["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Describe this."},
                {"type": "input_image", "image_url": "https://example.com/image.png"},
            ],
        }
    ]


def test_openai_codex_direct_image_payload_uses_responses_image_tool():
    input_items = _build_openai_codex_direct_image_input(
        [
            {"type": "text", "text": "A watercolor cabin"},
            {"type": "image_url", "image_url": {"url": "https://example.com/ref.png"}},
        ],
        aspect_ratio="16:9",
        resolution="1024x576",
    )
    payload = _build_openai_codex_direct_image_payload(
        model="openai-codex/gpt-5.5",
        input_items=input_items,
    )
    pro_payload = _build_openai_codex_direct_image_payload(
        model="openai-codex/gpt-5.5-pro:image-generation",
        input_items=input_items,
    )

    assert payload["model"] == "gpt-5.5"
    assert pro_payload["model"] == "gpt-5.5"
    assert "image generation assistant" in payload["instructions"]
    assert payload["stream"] is True
    assert payload["store"] is False
    assert payload["tools"] == [
        {"type": "image_generation", "action": "generate", "partial_images": 0}
    ]
    assert input_items[0]["content"][0]["text"].startswith("A watercolor cabin")
    assert "Aspect ratio: 16:9" in input_items[0]["content"][0]["text"]
    assert input_items[0]["content"][1] == {
        "type": "input_image",
        "image_url": "https://example.com/ref.png",
    }


def test_openai_codex_direct_image_result_decodes_completed_response_output():
    encoded = base64.b64encode(b"fake-png").decode()

    assert _extract_openai_codex_direct_image_result(
        {"response": {"output": [{"type": "image_generation_call", "result": encoded}]}}
    ) == (b"fake-png", "png")


def test_openai_codex_image_generation_uses_direct_responses_without_runtime():
    req = _openai_codex_test_req()
    encoded = base64.b64encode(b"fake-png").decode()
    calls: dict[str, Any] = {}

    class ImageStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield (
                "event: response.completed\n"
                f'data: {{"response":{{"output":[{{"type":"image_generation_call","result":"{encoded}"}}]}}}}\n\n'
            ).encode()

    class StreamContext:
        async def __aenter__(self):
            return httpx.Response(200, stream=ImageStream())

        async def __aexit__(self, *_args):
            return False

    class FakeClient:
        def stream(self, method, endpoint, *, headers, json):
            calls["method"] = method
            calls["endpoint"] = endpoint
            calls["headers"] = headers
            calls["payload"] = json
            return StreamContext()

    with patch("services.openai_codex._build_runtime_context", side_effect=AssertionError):
        generated = asyncio.run(
            generate_image_with_openai_codex(
                auth_json=req.auth_json,
                model="openai-codex/gpt-5.5",
                message_content="A tiny robot painting",
                aspect_ratio="1:1",
                resolution="1024x1024",
                http_client=FakeClient(),
            )
        )

    assert generated.image_bytes == b"fake-png"
    assert generated.extension == "png"
    assert generated.model == "openai-codex/gpt-5.5"
    assert calls["method"] == "POST"
    assert calls["endpoint"] == "https://chatgpt.com/backend-api/codex/responses"
    assert calls["payload"]["tools"][0]["type"] == "image_generation"


def test_openai_codex_responses_usage_normalizes_token_details():
    usage = _normalize_openai_responses_usage_data(
        {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "input_tokens_details": {"cached_tokens": 3},
            "output_tokens_details": {"reasoning_tokens": 2},
        }
    )

    assert usage == {
        "cost": 0.0,
        "is_byok": False,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "prompt_tokens_details": {"cached_tokens": 3},
        "completion_tokens_details": {"reasoning_tokens": 2},
    }


def test_openai_codex_sse_parser_handles_split_chunks():
    class ChunkedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'event: response.output_text.delta\ndata: {"delta":"Hel'
            yield b'lo"}\n\nevent: response.completed\ndata: {"usage":{"total_tokens":1}}\n\n'

    async def _collect():
        response = httpx.Response(200, stream=ChunkedStream())
        return [event async for event in _iter_openai_codex_sse_events(response)]

    assert asyncio.run(_collect()) == [
        ("response.output_text.delta", {"delta": "Hello"}),
        ("response.completed", {"usage": {"total_tokens": 1}}),
    ]


def test_openai_codex_non_streaming_uses_direct_runner_without_runtime():
    req = _openai_codex_test_req()

    async def _direct_runner(*_args, **kwargs):
        kwargs["usage_data_sink"].update({"prompt_tokens": 1, "completion_tokens": 1})
        return "direct response"

    async def _persist_refreshed_auth_json(**_kwargs):
        return None

    async def _update_node_usage_data(**_kwargs):
        return None

    with (
        patch("services.openai_codex._run_openai_codex_direct_turn", _direct_runner),
        patch("services.openai_codex._build_runtime_context", side_effect=AssertionError),
        patch("services.openai_codex._persist_refreshed_auth_json", _persist_refreshed_auth_json),
        patch("services.openai_codex.update_node_usage_data", _update_node_usage_data),
    ):
        response = asyncio.run(make_openai_codex_request_non_streaming(req, None))

    assert response == "direct response"


def test_ask_user_arguments_drop_empty_codex_optional_fields():
    parsed = AskUserArguments.model_validate(
        {
            "title": "Image details",
            "questions": [
                {
                    "id": "subject",
                    "options": [],
                    "question": "What should the image show?",
                    "help_text": "Describe the subject, scene, style, and any important details.",
                    "input_type": "text",
                    "validation": {
                        "placeholder": "Example: a cozy cabin in a snowy forest at sunset"
                    },
                    "allow_other": False,
                },
                {
                    "id": "aspect",
                    "options": [{"label": "Square", "value": "1:1"}],
                    "question": "What aspect ratio do you want?",
                    "help_text": "",
                    "input_type": "single_select",
                    "validation": {"placeholder": ""},
                    "allow_other": False,
                },
            ],
        }
    )

    dumped = parsed.dump_public()
    assert "options" not in dumped["questions"][0]
    assert dumped["questions"][0]["validation"]["placeholder"].startswith("Example:")
    assert dumped["questions"][1]["options"] == [{"label": "Square", "value": "1:1"}]
    assert "validation" not in dumped["questions"][1]


def test_openai_codex_direct_runner_stops_after_ask_user_pending():
    req = _openai_codex_test_req()
    calls = {"stream": 0}

    async def _stream_one_request(self, *_args, **_kwargs):
        calls["stream"] += 1
        if calls["stream"] > 1:
            raise AssertionError("Codex should wait for user input before another request.")
        return [
            {
                "type": "function_call",
                "name": "ask_user",
                "call_id": "call-1",
                "arguments": '{"questions":[{"question":"Continue?","input_type":"boolean"}]}',
            }
        ]

    async def _direct_tool_call(**kwargs):
        assert kwargs["mixed_tool_round"] is False
        kwargs["state"].awaiting_user_input = True
        return {"type": "function_call_output", "call_id": "call-1", "output": "{}"}

    with (
        patch(
            "services.openai_codex._OpenAICodexDirectTurnRunner._stream_one_request",
            _stream_one_request,
        ),
        patch("services.openai_codex._run_openai_codex_direct_tool_call", _direct_tool_call),
    ):
        response = asyncio.run(_OpenAICodexDirectTurnRunner(req, req.auth_json).run())

    assert response == ""
    assert calls["stream"] == 1


def test_extract_openai_codex_reasoning_item_text_prefers_summary_then_content():
    assert (
        _extract_reasoning_item_text(
            {
                "type": "reasoning",
                "summary": [
                    {"type": "summary_text", "text": "Plan approach."},
                    {"type": "summary_text", "text": "Check edge cases."},
                ],
                "content": [{"type": "reasoning_text", "text": "Detailed chain."}],
            }
        )
        == "Plan approach.\n\nCheck edge cases.\n\nDetailed chain."
    )


def test_openai_codex_extract_system_instructions_joins_system_messages_only():
    assert (
        _extract_system_instructions(
            [
                {"role": "system", "content": [{"type": "text", "text": "Rule one."}]},
                {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
                {"role": "system", "content": [{"type": "text", "text": "Rule two."}]},
            ]
        )
        == "Rule one.\n\nRule two."
    )


def test_openai_codex_sanitize_model_instructions_removes_external_tool_lines():
    sanitized = _sanitize_model_instructions(
        """
You are Meridian.

- `functions.update_plan` — update a task plan
- `functions.apply_patch` — edit files with a patch
- `multi_tool_use.parallel` — run multiple developer tools in parallel

Keep answers concise.
"""
    )

    assert "functions.update_plan" not in sanitized
    assert "functions.apply_patch" not in sanitized
    assert "multi_tool_use.parallel" not in sanitized
    assert "You are Meridian." in sanitized
    assert "Keep answers concise." in sanitized
    assert "only use the tools explicitly exposed by the host runtime" in sanitized


def test_sanitize_external_tool_references_keeps_safe_lines_and_appends_disclaimer_once():
    sanitized = sanitize_external_tool_references(
        """
Keep answers concise.

functions.request_user_input should not appear.
Use only tools available in Meridian.
multi_tool_use.parallel also should not appear.
"""
    )

    assert "functions.request_user_input" not in sanitized
    assert "multi_tool_use.parallel" not in sanitized
    assert "Keep answers concise." in sanitized
    assert "Use only tools available in Meridian." in sanitized
    assert sanitized.count("only use the tools explicitly exposed by the host runtime") == 1


def test_openai_codex_validate_request_allows_tools_and_rejects_files():
    req = OpenAICodexReqChat(
        auth_json='{"access_token":"test"}',
        model="openai-codex/gpt-5.4",
        messages=[{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
        config=SimpleNamespace(exclude_reasoning=False, reasoning_effort="low"),
        user_id="user-1",
        pg_engine=None,
        selected_tools=[ToolEnum.WEB_SEARCH],
    )

    req.validate_request()

    req.messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "filename": "example.pdf",
                        "file_data": "data:application/pdf;base64,AAA=",
                    },
                }
            ],
        }
    ]

    try:
        req.validate_request()
    except ValueError as exc:
        assert "text and image inputs" in str(exc)
    else:  # pragma: no cover - defensive regression guard
        raise AssertionError("Expected OpenAI Codex file validation to fail.")


def test_openai_codex_dynamic_tools_map_link_extraction_to_fetch_page_content():
    dynamic_tools = _build_dynamic_tools(
        [
            ToolEnum.WEB_SEARCH,
            ToolEnum.LINK_EXTRACTION,
            ToolEnum.EXECUTE_CODE,
            ToolEnum.ASK_USER,
        ]
    )

    assert [tool["name"] for tool in dynamic_tools] == [
        "web_search",
        "fetch_page_content",
        "execute_code",
        "ask_user",
    ]
    assert all(isinstance(tool.get("inputSchema"), dict) for tool in dynamic_tools)


def test_openai_codex_build_pending_assistant_message_uses_function_tool_call_shape():
    message = _build_pending_assistant_message(
        tool_name=ToolEnum.ASK_USER.value,
        tool_call_id="call_123",
        arguments={"question": "Need choice", "input_type": "text"},
        assistant_text="Need your input first.",
    )

    assert message["role"] == "assistant"
    assert message["content"] == "Need your input first."
    assert message["tool_calls"] == [
        {
            "type": "function",
            "id": "call_123",
            "function": {
                "name": ToolEnum.ASK_USER.value,
                "arguments": '{"question":"Need choice","input_type":"text"}',
            },
        }
    ]


def test_normalize_codex_usage_data_prefers_last_breakdown():
    usage_data = _normalize_codex_usage_data(
        {
            "last": {
                "inputTokens": 120,
                "cachedInputTokens": 20,
                "outputTokens": 30,
                "reasoningOutputTokens": 7,
                "totalTokens": 150,
            },
            "total": {
                "inputTokens": 999,
                "cachedInputTokens": 999,
                "outputTokens": 999,
                "reasoningOutputTokens": 999,
                "totalTokens": 999,
            },
        }
    )

    assert usage_data == {
        "cost": 0.0,
        "is_byok": False,
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "prompt_tokens_details": {"cached_tokens": 20},
        "completion_tokens_details": {"reasoning_tokens": 7},
    }


def test_openai_codex_validate_request_rejects_file_attachments():
    req = OpenAICodexReqChat(
        auth_json='{"access_token":"test"}',
        model="openai-codex/gpt-5.4",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "file",
                        "file": {
                            "filename": "example.pdf",
                            "file_data": "data:application/pdf;base64,AAA=",
                        },
                    }
                ],
            }
        ],
        config=SimpleNamespace(exclude_reasoning=False, reasoning_effort="low"),
        user_id="user-1",
        pg_engine=None,
        selected_tools=[],
    )

    try:
        req.validate_request()
    except ValueError as exc:
        assert "text and image inputs" in str(exc)
    else:  # pragma: no cover - defensive regression guard
        raise AssertionError("Expected OpenAI Codex file validation to fail.")


async def _validate_only_default(_token: str, model_id: str) -> bool:
    return model_id == "claude-agent/default"


def test_claude_agent_catalog_validation_cache_filters_and_reuses_validated_aliases():
    validated_once = asyncio.run(
        get_claude_agent_models(
            oauth_token="test-token",
            validate_aliases=True,
            alias_validator=_validate_only_default,
        )
    )
    validated_twice = asyncio.run(
        get_claude_agent_models(
            oauth_token="test-token",
            validate_aliases=True,
            alias_validator=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("validation cache was not used")
            ),
        )
    )

    assert [model.id for model in validated_once] == ["claude-agent/default"]
    assert [model.id for model in validated_twice] == ["claude-agent/default"]


def test_z_ai_coding_plan_catalog_returns_models_dev_copies():
    models_dev_catalog = {
        "zai-coding-plan": {
            "models": {
                "glm-5.2": {
                    "id": "glm-5.2",
                    "name": "GLM-5.2",
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "limit": {"context": 1000000},
                    "cost": {"input": 0, "output": 0},
                }
            }
        }
    }

    models = asyncio.run(get_z_ai_coding_plan_models(models_dev_catalog))
    models[0].name = "Mutated"
    models_again = asyncio.run(get_z_ai_coding_plan_models(models_dev_catalog))

    assert [model.id for model in models_again] == ["z-ai-plan/glm-5.2"]
    assert models_again[0].name == "GLM-5.2"


def test_z_ai_coding_plan_catalog_returns_empty_without_models_dev_catalog():
    models = asyncio.run(get_z_ai_coding_plan_models())

    assert models == []


def test_opencode_go_catalog_returns_models_dev_copies():
    models_dev_catalog = {
        "opencode-go": {
            "models": {
                "glm-5": {
                    "id": "glm-5",
                    "name": "GLM-5",
                    "modalities": {"input": ["text"], "output": ["text"]},
                    "limit": {"context": 202752},
                    "cost": {"input": 1.4, "output": 4.4},
                }
            }
        }
    }

    models = asyncio.run(get_opencode_go_models(models_dev_catalog))
    models[0].name = "Mutated"
    models_again = asyncio.run(get_opencode_go_models(models_dev_catalog))

    assert [model.id for model in models_again] == ["opencode-go/glm-5"]
    assert models_again[0].name == "GLM-5"


def test_opencode_go_catalog_returns_empty_without_models_dev_catalog():
    models = asyncio.run(get_opencode_go_models())

    assert models == []


def test_gemini_cli_catalog_returns_copies():
    models = asyncio.run(get_gemini_cli_models())
    assert [model.id for model in models] == [model.id for model in GEMINI_CLI_MODELS]
    assert models is not GEMINI_CLI_MODELS
    assert all(model_a is not model_b for model_a, model_b in zip(models, GEMINI_CLI_MODELS))


def test_github_copilot_model_listing_dedupes_sorts_and_copies():
    _clear_github_copilot_model_cache()

    async def _model_lister():
        return [
            SimpleNamespace(
                id="gpt-5-mini",
                name="GPT-5 Mini",
                capabilities=SimpleNamespace(
                    supports=SimpleNamespace(vision=False),
                    limits=SimpleNamespace(max_context_window_tokens=128000),
                ),
            ),
            SimpleNamespace(
                id="gpt-5",
                name="GPT-5",
                capabilities=SimpleNamespace(
                    supports=SimpleNamespace(vision=True),
                    limits=SimpleNamespace(max_context_window_tokens=200000),
                ),
            ),
            SimpleNamespace(
                id="gpt-5",
                name="GPT-5 Duplicate",
                capabilities=SimpleNamespace(
                    supports=SimpleNamespace(vision=True),
                    limits=SimpleNamespace(max_context_window_tokens=200000),
                ),
            ),
        ]

    listed_models = asyncio.run(
        list_github_copilot_models("gho_test-token", model_lister=_model_lister, use_cache=False)
    )
    listed_models_by_id = {model.id: model for model in listed_models}

    assert "github-copilot/gpt-5" in listed_models_by_id
    assert "github-copilot/gpt-5-mini" in listed_models_by_id
    listed_models_by_id["github-copilot/gpt-5"].name = "changed"

    fresh_models = asyncio.run(
        list_github_copilot_models("gho_test-token", model_lister=_model_lister, use_cache=False)
    )
    fresh_models_by_id = {model.id: model for model in fresh_models}
    assert fresh_models_by_id["github-copilot/gpt-5"].name == "GPT-5"


def test_github_copilot_model_listing_returns_only_sdk_models():
    _clear_github_copilot_model_cache()

    async def _model_lister():
        return []

    listed_models = asyncio.run(
        list_github_copilot_models("gho_test-token", model_lister=_model_lister, use_cache=False)
    )

    assert listed_models == []


def test_github_copilot_sdk_model_listing_falls_back_to_raw_models_on_billing_parse_error():
    class FakeRpcClient:
        async def request(self, method, payload):
            assert method == "models.list"
            assert payload == {}
            return {
                "models": [
                    {
                        "id": "gpt-5",
                        "name": "GPT-5",
                        "capabilities": {
                            "supports": {"vision": True},
                            "limits": {"max_context_window_tokens": 200000},
                        },
                        "billing": {},
                    }
                ]
            }

    class FakeCopilotClient:
        def __init__(self, _config):
            self._client = FakeRpcClient()

        async def start(self):
            return None

        async def list_models(self):
            raise ValueError("Missing required field 'multiplier' in ModelBilling")

        async def force_stop(self):
            return None

    async def _stop_runtime_heartbeat(_heartbeat_task):
        return None

    with (
        patch("services.github_copilot.CopilotClient", FakeCopilotClient),
        patch(
            "services.github_copilot.SubprocessConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        ),
        patch(
            "services.github_copilot._build_runtime_context",
            return_value=SimpleNamespace(root_dir=Path("/tmp"), cwd=Path("/tmp"), env={}),
        ),
        patch("services.github_copilot.start_runtime_heartbeat", return_value=None),
        patch("services.github_copilot.stop_runtime_heartbeat", _stop_runtime_heartbeat),
        patch("services.github_copilot._cleanup_runtime_context"),
    ):
        raw_models = asyncio.run(_list_sdk_models("gho_test-token"))

    assert raw_models == [
        {
            "id": "gpt-5",
            "name": "GPT-5",
            "capabilities": {
                "supports": {"vision": True},
                "limits": {"max_context_window_tokens": 200000},
            },
            "billing": {},
        }
    ]


def test_get_github_copilot_models_safe_returns_empty_on_failure():
    with patch(
        "services.github_copilot.list_github_copilot_models",
        side_effect=RuntimeError("boom"),
    ):
        models = asyncio.run(get_github_copilot_models_safe("gho_test-token"))

    assert models == []


def test_get_openai_codex_models_safe_returns_warning_on_auth_failure():
    warnings = []
    auth_error = ValueError(
        "OpenAI Codex authentication is invalid or expired. "
        "Paste a fresh ~/.codex/auth.json file."
    )

    with patch("services.openai_codex.list_openai_codex_models", side_effect=auth_error):
        models = asyncio.run(
            get_openai_codex_models_safe(
                '{"access_token":"test"}',
                user_id="user-1",
                pg_engine=None,
                warnings=warnings,
            )
        )

    assert models == []
    assert len(warnings) == 1
    assert warnings[0].provider == InferenceProviderEnum.OPENAI_CODEX
    assert warnings[0].title == "OpenAI Codex needs reconnecting"
    assert warnings[0].message == str(auth_error)
    assert warnings[0].actionLabel == "Open provider settings"
    assert warnings[0].actionUrl == "/settings?tab=providers"


def test_openai_codex_models_dev_catalog_filters_codex_models():
    models = build_openai_codex_models_from_models_dev(
        {
            "openai": {
                "models": {
                    "gpt-5.4": {
                        "id": "gpt-5.4",
                        "name": "GPT-5.4",
                        "modalities": {"input": ["text", "image", "pdf"], "output": ["text"]},
                        "limit": {"context": 1050000},
                    },
                    "gpt-5.5-pro": {
                        "id": "gpt-5.5-pro",
                        "name": "GPT-5.5 Pro",
                        "modalities": {"input": ["text", "image"], "output": ["text"]},
                        "limit": {"context": 1050000},
                    },
                    "gpt-5.4-nano": {"id": "gpt-5.4-nano"},
                    "gpt-4.1": {"id": "gpt-4.1"},
                }
            }
        }
    )

    model_ids = [model.id for model in models]
    assert model_ids[0] == "openai-codex/gpt-5.4:image-generation"
    assert "openai-codex/gpt-5.5-pro" in model_ids
    assert "openai-codex/gpt-5.4" in model_ids
    assert "openai-codex/gpt-5.4-nano" not in model_ids
    assert "openai-codex/gpt-4.1" not in model_ids


def test_openai_codex_validation_forces_refresh_and_probes_auth():
    auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }
    )
    events = []

    async def _refresh_if_needed(auth_json_value: str, *, force: bool = False) -> str:
        events.append(("refresh", force))
        return auth_json_value

    async def _probe_auth(_auth_json_value: str) -> None:
        events.append(("probe", True))

    with (
        patch("services.openai_codex._refresh_openai_codex_auth_if_needed", _refresh_if_needed),
        patch("services.openai_codex._probe_openai_codex_auth", _probe_auth),
    ):
        normalized_auth_json = asyncio.run(validate_openai_codex_oauth_auth_json(auth_json))

    assert normalized_auth_json == auth_json
    assert events == [("refresh", True), ("probe", True)]


def test_openai_codex_device_oauth_uses_redis_for_cross_worker_completion():
    class FakeRedisClient:
        def __init__(self):
            self.values: dict[str, str] = {}

        async def set(self, key: str, value: str, ex: int):
            assert ex > 0
            self.values[key] = value

        async def get(self, key: str):
            return self.values.get(key)

        async def delete(self, key: str):
            self.values.pop(key, None)

    class FakeRedisManager:
        def __init__(self):
            self.client = FakeRedisClient()

    responses = [
        httpx.Response(
            200,
            json={"device_auth_id": "device-auth-id", "user_code": "CODE-123", "interval": 1},
        ),
        httpx.Response(
            200,
            json={"authorization_code": "authorization-code", "code_verifier": "code-verifier"},
        ),
    ]

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return responses.pop(0)

    async def _exchange_code(*, code: str, redirect_uri: str, code_verifier: str):
        assert code == "authorization-code"
        assert redirect_uri == "https://auth.openai.com/deviceauth/callback"
        assert code_verifier == "code-verifier"
        return {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }

    async def _run():
        redis_manager = FakeRedisManager()
        _openai_codex_device_sessions.clear()
        try:
            start_result = await start_openai_codex_device_oauth(redis_manager)

            # Simulate production's multi-worker handoff: the completing worker has no local dict.
            _openai_codex_device_sessions.clear()

            auth_json = await complete_openai_codex_device_oauth(
                start_result["session_id"],
                redis_manager,
            )
            assert json.loads(auth_json)["tokens"]["refresh_token"] == "refresh-token"
            assert redis_manager.client.values == {}
        finally:
            _openai_codex_device_sessions.clear()

    with (
        patch("services.openai_codex.httpx.AsyncClient", FakeAsyncClient),
        patch("services.openai_codex._exchange_openai_codex_code", _exchange_code),
    ):
        asyncio.run(_run())

    assert responses == []


def test_openai_codex_device_oauth_falls_back_when_redis_commands_fail():
    class FailingRedisClient:
        async def set(self, *_args, **_kwargs):
            raise ConnectionError("redis unavailable")

        async def get(self, *_args, **_kwargs):
            raise ConnectionError("redis unavailable")

        async def delete(self, *_args, **_kwargs):
            raise ConnectionError("redis unavailable")

    class FailingRedisManager:
        def __init__(self):
            self.client = FailingRedisClient()

    responses = [
        httpx.Response(
            200,
            json={"device_auth_id": "device-auth-id", "user_code": "CODE-123", "interval": 1},
        ),
        httpx.Response(
            200,
            json={"authorization_code": "authorization-code", "code_verifier": "code-verifier"},
        ),
    ]

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return responses.pop(0)

    async def _exchange_code(*, code: str, redirect_uri: str, code_verifier: str):
        assert code == "authorization-code"
        assert redirect_uri == "https://auth.openai.com/deviceauth/callback"
        assert code_verifier == "code-verifier"
        return {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }

    async def _run():
        redis_manager = FailingRedisManager()
        _openai_codex_device_sessions.clear()
        try:
            start_result = await start_openai_codex_device_oauth(redis_manager)
            assert start_result["session_id"] in _openai_codex_device_sessions

            auth_json = await complete_openai_codex_device_oauth(
                start_result["session_id"],
                redis_manager,
            )
            assert json.loads(auth_json)["tokens"]["refresh_token"] == "refresh-token"
            assert _openai_codex_device_sessions == {}
        finally:
            _openai_codex_device_sessions.clear()

    with (
        patch("services.openai_codex.httpx.AsyncClient", FakeAsyncClient),
        patch("services.openai_codex._exchange_openai_codex_code", _exchange_code),
    ):
        asyncio.run(_run())

    assert responses == []


def test_openai_codex_auth_probe_payload_includes_required_instructions():
    auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }
    )
    calls: dict[str, Any] = {}

    class ProbeStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'event: response.completed\ndata: {"response":{"output":[]}}\n\n'

    class StreamContext:
        async def __aenter__(self):
            return httpx.Response(200, stream=ProbeStream())

        async def __aexit__(self, *_args):
            return False

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def stream(self, method, endpoint, *, headers, json):
            calls["method"] = method
            calls["endpoint"] = endpoint
            calls["headers"] = headers
            calls["payload"] = json
            return StreamContext()

    with patch("services.openai_codex.httpx.AsyncClient", FakeAsyncClient):
        asyncio.run(_probe_openai_codex_auth(auth_json))

    assert calls["method"] == "POST"
    assert calls["endpoint"] == "https://chatgpt.com/backend-api/codex/responses"
    assert calls["payload"]["instructions"]
    assert "max_output_tokens" not in calls["payload"]


def test_openai_codex_model_discovery_validates_before_catalog_fetch():
    auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }
    )
    events = []

    async def _validate_auth(auth_json_value: str) -> str:
        events.append("validate")
        return auth_json_value

    async def _fetch_catalog(_models_dev_catalog):
        events.append("catalog")
        return []

    with (
        patch("services.openai_codex._validate_openai_codex_auth_tokens", _validate_auth),
        patch("services.openai_codex.get_models_dev_openai_codex_models", _fetch_catalog),
    ):
        models = asyncio.run(list_openai_codex_models(auth_json, models_dev_catalog={}))

    assert models == []
    assert events == ["validate", "catalog"]


def test_openai_codex_model_discovery_rejects_invalid_auth_before_catalog_fetch():
    async def _validate_auth(_auth_json_value: str) -> str:
        raise ValueError("bad codex auth")

    async def _fetch_catalog(_models_dev_catalog):  # pragma: no cover - defensive regression guard
        raise AssertionError("catalog should not be fetched before auth validation")

    with (
        patch("services.openai_codex._validate_openai_codex_auth_tokens", _validate_auth),
        patch("services.openai_codex.get_models_dev_openai_codex_models", _fetch_catalog),
    ):
        try:
            asyncio.run(list_openai_codex_models("{}", models_dev_catalog={}))
        except ValueError as exc:
            assert "bad codex auth" in str(exc)
        else:  # pragma: no cover - defensive regression guard
            raise AssertionError("Expected invalid Codex auth to fail before catalog fetch.")


def test_openai_codex_model_discovery_returns_empty_when_models_dev_fails():
    auth_json = _build_codex_auth_json_from_tokens(
        {
            "id_token": _unsigned_jwt({}),
            "access_token": _unsigned_jwt({"exp": 4102444800}),
            "refresh_token": "refresh-token",
        }
    )

    async def _validate_auth(auth_json_value: str) -> str:
        return auth_json_value

    with (
        patch("services.openai_codex._validate_openai_codex_auth_tokens", _validate_auth),
        patch(
            "services.openai_codex.get_models_dev_openai_codex_models",
            side_effect=RuntimeError("models.dev unavailable"),
        ),
    ):
        models = asyncio.run(list_openai_codex_models(auth_json, models_dev_catalog={}))

    assert models == []


def test_format_model_unavailable_error_mentions_cli_scope():
    message = _format_model_unavailable_error("github-copilot/gemini-3.1-pro")

    assert '"gemini-3.1-pro"' in message
    assert "subscription" in message
    assert "Copilot CLI" in message
    assert "plan/model access" in message


def test_github_copilot_unsupported_model_error_uses_public_subscription_message():
    raw_error = RuntimeError(
        "Execution failed: CAPIError: 400 The requested model is not supported. "
        "(Request ID: test)"
    )

    assert _is_model_unavailable_error(raw_error, "github-copilot/gpt-5") is True

    message = _public_github_copilot_stream_error_message(raw_error, "github-copilot/gpt-5")

    assert '"gpt-5"' in message
    assert "subscription" in message
    assert "choose another GitHub Copilot model" in message
    assert "unexpected server error" not in message.lower()


def test_github_copilot_stream_emits_public_unsupported_model_error():
    req = GitHubCopilotReqChat(
        github_token="gho_test-token",
        model="github-copilot/gpt-5",
        messages=[{"role": "user", "content": "Hello"}],
        config=SimpleNamespace(exclude_reasoning=False, reasoning_effort="low"),
        user_id="user-1",
        pg_engine=None,
    )

    async def _raise_unsupported_model(*_args, **_kwargs):
        raise RuntimeError(
            "Execution failed: CAPIError: 400 The requested model is not supported. "
            "(Request ID: test)"
        )

    async def _collect_chunks():
        chunks = []
        with patch("services.github_copilot._run_copilot_session", _raise_unsupported_model):
            async for chunk in stream_github_copilot_response(req, None, None):
                chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect_chunks())
    expected_message = _format_model_unavailable_error("github-copilot/gpt-5")

    assert chunks == [f"[ERROR]{expected_message}[!ERROR]"]


def test_build_copilot_system_message_removes_host_sections_and_scopes_tools():
    system_message = _build_copilot_system_message(
        "You are Meridian.",
        ["web_search", "execute_code"],
    )

    assert system_message["mode"] == "customize"
    assert system_message["sections"]["identity"] == {"action": "remove"}
    assert system_message["sections"]["tool_instructions"] == {"action": "remove"}
    assert "authoritative instruction set" in system_message["content"]
    assert "web_search, execute_code" in system_message["content"]


def test_github_copilot_validate_request_allows_ask_user_without_http_client():
    req = GitHubCopilotReqChat(
        github_token="gho_test-token",
        model="github-copilot/gpt-5",
        messages=[{"role": "user", "content": "Need clarification."}],
        config=SimpleNamespace(exclude_reasoning=False, reasoning_effort="low"),
        user_id="user-1",
        pg_engine=None,
        selected_tools=[ToolEnum.ASK_USER],
    )

    req.validate_request()


def test_github_copilot_non_streaming_rejects_ask_user():
    req = GitHubCopilotReqChat(
        github_token="gho_test-token",
        model="github-copilot/gpt-5",
        messages=[{"role": "user", "content": "Need clarification."}],
        config=SimpleNamespace(exclude_reasoning=False, reasoning_effort="low"),
        user_id="user-1",
        pg_engine=None,
        selected_tools=[ToolEnum.ASK_USER],
    )

    try:
        asyncio.run(make_github_copilot_request_non_streaming(req, None))
    except ValueError as exc:
        assert str(exc) == "GitHub Copilot ask_user requires streaming mode."
    else:  # pragma: no cover - defensive regression guard
        raise AssertionError("Expected GitHub Copilot ask_user to require streaming mode.")


def test_extract_bridge_json_payload_accepts_clean_json():
    assert extract_bridge_json_payload('{"ok":true,"value":1}') == {
        "ok": True,
        "value": 1,
    }


def test_extract_bridge_json_payload_recovers_json_after_bridge_noise():
    noisy_stdout = 'Cached credentials are invalid.\n\n{"ok":false,"error":"bad creds"}'
    assert extract_bridge_json_payload(noisy_stdout) == {
        "ok": False,
        "error": "bad creds",
    }
