from typing import Literal, TypedDict

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from models.message import ToolEnum

OPENCODE_GO_PROVIDER_KEY = "opencode_go.api_key"
OPENCODE_GO_MODEL_PREFIX = "opencode-go/"
OPENCODE_GO_LABEL = "OpenCode Go"
OPENCODE_GO_SUPPORTED_TOOL_NAMES = [
    ToolEnum.WEB_SEARCH.value,
    ToolEnum.LINK_EXTRACTION.value,
    ToolEnum.EXECUTE_CODE.value,
    ToolEnum.IMAGE_GENERATION.value,
    ToolEnum.VISUALISE.value,
    ToolEnum.ASK_USER.value,
]


class OpenCodeGoModelDefinition(TypedDict):
    id: str
    name: str
    protocol: Literal["anthropic", "openai"]


OPENCODE_GO_MODEL_DEFINITIONS: list[OpenCodeGoModelDefinition] = [
    {"id": "glm-5", "name": "GLM-5", "protocol": "openai"},
    {"id": "glm-5.1", "name": "GLM-5.1", "protocol": "openai"},
    {"id": "kimi-k2.5", "name": "Kimi K2.5", "protocol": "openai"},
    {"id": "mimo-v2-pro", "name": "MiMo-V2-Pro", "protocol": "openai"},
    {"id": "mimo-v2-omni", "name": "MiMo-V2-Omni", "protocol": "openai"},
    {"id": "minimax-m2.5", "name": "MiniMax M2.5", "protocol": "anthropic"},
    {"id": "minimax-m2.7", "name": "MiniMax M2.7", "protocol": "anthropic"},
    {"id": "qwen3.5-plus", "name": "Qwen3.5 Plus", "protocol": "openai"},
    {"id": "qwen3.6-plus", "name": "Qwen3.6 Plus", "protocol": "openai"},
]

OPENCODE_GO_ANTHROPIC_MODEL_IDS = {
    definition["id"]
    for definition in OPENCODE_GO_MODEL_DEFINITIONS
    if definition["protocol"] == "anthropic"
}


def _build_opencode_go_model(model_definition: OpenCodeGoModelDefinition) -> ModelInfo:
    return ModelInfo(
        id=f"{OPENCODE_GO_MODEL_PREFIX}{model_definition['id']}",
        name=model_definition["name"],
        icon="opencode",
        architecture=Architecture(
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="opencode",
        ),
        context_length=-1,
        pricing=Pricing(prompt="0", completion="0"),
        provider=InferenceProviderEnum.OPENCODE_GO,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=True,
        supportedMeridianToolNames=list(OPENCODE_GO_SUPPORTED_TOOL_NAMES),
        toolsSupport=False,
    )


OPENCODE_GO_MODELS = [
    _build_opencode_go_model(model_definition) for model_definition in OPENCODE_GO_MODEL_DEFINITIONS
]


async def get_opencode_go_models() -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in OPENCODE_GO_MODELS]
