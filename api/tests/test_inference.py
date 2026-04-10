import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.inference import (
    CLAUDE_AGENT_SUPPORTED_TOOL_NAMES,
    Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES,
    get_supported_meridian_tool_names,
    model_supports_structured_outputs,
    normalize_openrouter_model,
    resolve_model_provider,
)
from services.providers.claude_agent_catalog import (
    CLAUDE_AGENT_MODELS,
    get_claude_agent_models,
)
from services.providers.z_ai_coding_plan_catalog import (
    Z_AI_CODING_PLAN_MODELS,
    get_z_ai_coding_plan_models,
)


def test_resolve_model_provider_uses_prefix_for_claude_agent():
    assert resolve_model_provider("claude-agent/sonnet") == InferenceProviderEnum.CLAUDE_AGENT
    assert (
        resolve_model_provider("z-ai-plan/glm-5.1") == InferenceProviderEnum.Z_AI_CODING_PLAN
    )
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
            "claude-agent/sonnet", [model.model_dump(mode="json") for model in CLAUDE_AGENT_MODELS]
        )
        is False
    )
    assert model_supports_structured_outputs("claude-agent/sonnet", CLAUDE_AGENT_MODELS) is False


def test_supported_meridian_tools_are_provider_specific():
    assert get_supported_meridian_tool_names("claude-agent/sonnet") == CLAUDE_AGENT_SUPPORTED_TOOL_NAMES
    assert (
        get_supported_meridian_tool_names("z-ai-plan/glm-5.1")
        == Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES
    )
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
