import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from models.message import ToolEnum
from services.github_copilot import (
    GitHubCopilotReqChat,
    _build_copilot_system_message,
    _clear_github_copilot_model_cache,
    _format_model_unavailable_error,
    list_github_copilot_models,
    make_github_copilot_request_non_streaming,
)
from services.inference import (
    CLAUDE_AGENT_SUPPORTED_TOOL_NAMES,
    GEMINI_CLI_SUPPORTED_TOOL_NAMES,
    GITHUB_COPILOT_SUPPORTED_TOOL_NAMES,
    Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES,
    get_github_copilot_models_safe,
    get_supported_meridian_tool_names,
    model_supports_structured_outputs,
    normalize_openrouter_model,
    resolve_model_provider,
)
from services.providers.claude_agent_catalog import CLAUDE_AGENT_MODELS, get_claude_agent_models
from services.providers.gemini_cli_bridge_utils import extract_bridge_json_payload
from services.providers.gemini_cli_catalog import GEMINI_CLI_MODELS, get_gemini_cli_models
from services.providers.github_copilot_catalog import normalize_github_copilot_model
from services.providers.z_ai_coding_plan_catalog import (
    Z_AI_CODING_PLAN_MODELS,
    get_z_ai_coding_plan_models,
)


def test_resolve_model_provider_uses_prefix_for_claude_agent():
    assert resolve_model_provider("claude-agent/sonnet") == InferenceProviderEnum.CLAUDE_AGENT
    assert resolve_model_provider("z-ai-plan/glm-5.1") == InferenceProviderEnum.Z_AI_CODING_PLAN
    assert resolve_model_provider("github-copilot/gpt-5") == InferenceProviderEnum.GITHUB_COPILOT
    assert resolve_model_provider("gemini-cli/flash") == InferenceProviderEnum.GEMINI_CLI
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
    assert Z_AI_CODING_PLAN_MODELS
    for model in Z_AI_CODING_PLAN_MODELS:
        assert model.provider == InferenceProviderEnum.Z_AI_CODING_PLAN
        assert model.billingType == BillingTypeEnum.SUBSCRIPTION
        assert model.supportsStructuredOutputs is False
        assert model.supportsMeridianTools is True
        assert model.supportedMeridianToolNames == Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES


def test_gemini_cli_catalog_is_subscription_only_and_structured():
    assert GEMINI_CLI_MODELS
    for model in GEMINI_CLI_MODELS:
        assert model.provider == InferenceProviderEnum.GEMINI_CLI
        assert model.billingType == BillingTypeEnum.SUBSCRIPTION
        assert model.supportsStructuredOutputs is True
        assert model.supportsMeridianTools is True
        assert model.supportedMeridianToolNames == GEMINI_CLI_SUPPORTED_TOOL_NAMES


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


def test_model_supports_structured_outputs_reads_dict_and_model_instances():
    assert (
        model_supports_structured_outputs(
            "claude-agent/sonnet",
            [model.model_dump(mode="json") for model in CLAUDE_AGENT_MODELS],
        )
        is False
    )
    assert model_supports_structured_outputs("claude-agent/sonnet", CLAUDE_AGENT_MODELS) is False


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
    assert "ask_user" in get_supported_meridian_tool_names("openai/gpt-4o-mini")


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


def test_z_ai_coding_plan_catalog_returns_copies():
    models = asyncio.run(get_z_ai_coding_plan_models())
    assert [model.id for model in models] == [model.id for model in Z_AI_CODING_PLAN_MODELS]
    assert models is not Z_AI_CODING_PLAN_MODELS
    assert all(model_a is not model_b for model_a, model_b in zip(models, Z_AI_CODING_PLAN_MODELS))


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


def test_get_github_copilot_models_safe_returns_empty_on_failure():
    with patch(
        "services.github_copilot.list_github_copilot_models",
        side_effect=RuntimeError("boom"),
    ):
        models = asyncio.run(get_github_copilot_models_safe("gho_test-token"))

    assert models == []


def test_format_model_unavailable_error_mentions_cli_scope():
    message = _format_model_unavailable_error("github-copilot/gemini-3.1-pro")

    assert '"gemini-3.1-pro"' in message
    assert "VS Code" in message
    assert "Copilot CLI" in message


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
