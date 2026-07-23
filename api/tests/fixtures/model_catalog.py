from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelDiscoveryWarning,
    ModelInfo,
    Pricing,
    ResponseModel,
)
from models.message import ToolEnum

OUTPUT_MODALITY_COMBINATIONS = (
    ["text"],
    ["image"],
    ["video"],
    ["text", "image"],
    ["text", "video"],
    ["image", "video"],
    ["text", "image", "video"],
)

SUBSCRIPTION_PROVIDERS = (
    InferenceProviderEnum.CLAUDE_AGENT,
    InferenceProviderEnum.GITHUB_COPILOT,
    InferenceProviderEnum.Z_AI_CODING_PLAN,
    InferenceProviderEnum.GEMINI_CLI,
    InferenceProviderEnum.OPENAI_CODEX,
    InferenceProviderEnum.OPENCODE_GO,
    InferenceProviderEnum.ALIBABA_TOKEN_PLAN,
)

ALL_MERIDIAN_TOOLS = [tool.value for tool in ToolEnum]


def build_representative_model_catalog() -> ResponseModel:
    models: list[ModelInfo] = []
    model_count = 510
    openrouter_count = 450

    for index in range(model_count):
        is_subscription = index >= openrouter_count
        provider = (
            SUBSCRIPTION_PROVIDERS[(index - openrouter_count) % len(SUBSCRIPTION_PROVIDERS)]
            if is_subscription
            else InferenceProviderEnum.OPENROUTER
        )
        output_modalities = OUTPUT_MODALITY_COMBINATIONS[index % len(OUTPUT_MODALITY_COMBINATIONS)]
        missing_optionals = index % 29 == 0
        supports_meridian_tools = index % 3 != 0
        supported_tools = (
            ALL_MERIDIAN_TOOLS[: (index % len(ALL_MERIDIAN_TOOLS)) + 1]
            if supports_meridian_tools
            else []
        )

        models.append(
            ModelInfo(
                id=f"{provider.value}/representative-{index:03d}",
                name=f"Representative Model {index:03d}",
                icon=(
                    None if missing_optionals else f"https://assets.example/icons/{index % 17}.svg"
                ),
                provider=provider,
                billingType=(
                    BillingTypeEnum.SUBSCRIPTION if is_subscription else BillingTypeEnum.METERED
                ),
                created=None if missing_optionals else f"2026-{(index % 12) + 1:02d}-15",
                context_length=None if missing_optionals else 32768 + (index % 8) * 32768,
                architecture=Architecture(
                    input_modalities=["text", "image"] if index % 5 == 0 else ["text"],
                    instruct_type="chatml" if index % 4 == 0 else None,
                    modality=f"text->{'+'.join(output_modalities)}",
                    output_modalities=output_modalities,
                    tokenizer="RepresentativeTokenizer",
                ),
                pricing=Pricing(
                    prompt=f"{(index % 19) + 1}.25",
                    completion=f"{(index % 23) + 2}.5",
                    image=None if index % 4 else f"0.{(index % 9) + 1}",
                    internal_reasoning="0.4" if index % 9 == 0 else None,
                    request="0.01" if index % 7 == 0 else None,
                    video="0.2" if "video" in output_modalities else None,
                    web_search="0.003" if index % 6 == 0 else None,
                ),
                supportsStructuredOutputs=index % 2 == 0,
                supportsMeridianTools=supports_meridian_tools,
                supportedMeridianToolNames=supported_tools,
                toolsSupport=index % 2 == 1,
                reasoningEfforts=(-1, 0, 2, 8, 42)[index % 5],
                requiresConnection=is_subscription,
            )
        )

    return ResponseModel(
        data=models,
        warnings=[
            ModelDiscoveryWarning(
                provider=InferenceProviderEnum.GITHUB_COPILOT,
                title="Some models could not be discovered",
                message="The deterministic fixture preserves warning details.",
                actionLabel="Reconnect",
                actionUrl="/settings?tab=Providers",
            )
        ],
    )
