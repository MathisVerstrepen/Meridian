from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from models.message import ToolEnum

GEMINI_CLI_PROVIDER_KEY = "gemini_cli.oauth_creds_json"
GEMINI_CLI_MODEL_PREFIX = "gemini-cli/"
GEMINI_CLI_LABEL = "Gemini CLI"
GEMINI_CLI_SUPPORTED_TOOL_NAMES = [
    ToolEnum.WEB_SEARCH.value,
    ToolEnum.LINK_EXTRACTION.value,
    ToolEnum.EXECUTE_CODE.value,
    ToolEnum.IMAGE_GENERATION.value,
    ToolEnum.VISUALISE.value,
    ToolEnum.ASK_USER.value,
]

# Maintenance note:
# Keep this alias catalog aligned with the documented Gemini CLI aliases.
# Meridian intentionally exposes the stable alias surface instead of a dynamic
# per-account model list because Gemini CLI routing can vary by account access
# and preview-feature settings.
GEMINI_CLI_MODEL_DEFINITIONS = [
    ("auto", "Gemini CLI Auto"),
    ("pro", "Gemini CLI Pro"),
    ("flash", "Gemini CLI Flash"),
    ("flash-lite", "Gemini CLI Flash Lite"),
]


def _build_gemini_cli_model(alias: str, display_name: str) -> ModelInfo:
    return ModelInfo(
        id=f"{GEMINI_CLI_MODEL_PREFIX}{alias}",
        name=display_name,
        icon="google",
        architecture=Architecture(
            input_modalities=["text", "image", "file"],
            modality="text+file->text",
            output_modalities=["text"],
            tokenizer="gemini",
        ),
        context_length=1048576,
        pricing=Pricing(prompt="0", completion="0"),
        provider=InferenceProviderEnum.GEMINI_CLI,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=True,
        supportsMeridianTools=True,
        supportedMeridianToolNames=GEMINI_CLI_SUPPORTED_TOOL_NAMES,
        toolsSupport=True,
    )


GEMINI_CLI_MODELS = [
    _build_gemini_cli_model(alias, display_name)
    for alias, display_name in GEMINI_CLI_MODEL_DEFINITIONS
]


async def get_gemini_cli_models() -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in GEMINI_CLI_MODELS]
