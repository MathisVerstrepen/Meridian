from typing import TypedDict

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from models.message import ToolEnum

Z_AI_CODING_PLAN_PROVIDER_KEY = "z_ai_coding_plan.api_key"
Z_AI_CODING_PLAN_MODEL_PREFIX = "z-ai-plan/"
Z_AI_CODING_PLAN_LABEL = "Z.AI Coding Plan"
Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES = [
    ToolEnum.WEB_SEARCH.value,
    ToolEnum.LINK_EXTRACTION.value,
    ToolEnum.EXECUTE_CODE.value,
    ToolEnum.IMAGE_GENERATION.value,
    ToolEnum.VISUALISE.value,
    ToolEnum.ASK_USER.value,
]


class ZAiCodingPlanModelDefinition(TypedDict):
    id: str
    name: str
    created: str
    context_length: int
    pricing: Pricing


# Keep this catalog aligned with the documented Coding Plan models only.
Z_AI_CODING_PLAN_MODEL_DEFINITIONS: list[ZAiCodingPlanModelDefinition] = [
    {
        "id": "glm-5.1",
        "name": "GLM-5.1",
        "created": "2026-04-07",
        "context_length": 203000,
        "pricing": Pricing(prompt="1.40", completion="4.40"),
    },
    {
        "id": "glm-5-turbo",
        "name": "GLM-5 Turbo",
        "created": "2026-03-15",
        "context_length": 203000,
        "pricing": Pricing(prompt="1.20", completion="4.00"),
    },
    {
        "id": "glm-4.7",
        "name": "GLM-4.7",
        "created": "2025-12-22",
        "context_length": 200000,
        "pricing": Pricing(prompt="0.60", completion="2.20"),
    },
    {
        "id": "glm-4.5-air",
        "name": "GLM-4.5 Air",
        "created": "2025-07-25",
        "context_length": 131000,
        "pricing": Pricing(prompt="0.20", completion="1.10"),
    },
]


def _build_z_ai_coding_plan_model(model_definition: ZAiCodingPlanModelDefinition) -> ModelInfo:
    return ModelInfo(
        id=f"{Z_AI_CODING_PLAN_MODEL_PREFIX}{model_definition['id']}",
        name=model_definition["name"],
        icon="z-ai",
        architecture=Architecture(
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="glm",
        ),
        context_length=model_definition["context_length"],
        created=model_definition["created"],
        pricing=model_definition["pricing"],
        provider=InferenceProviderEnum.Z_AI_CODING_PLAN,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=True,
        supportedMeridianToolNames=Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES,
        toolsSupport=True,
    )


Z_AI_CODING_PLAN_MODELS = [
    _build_z_ai_coding_plan_model(model_definition)
    for model_definition in Z_AI_CODING_PLAN_MODEL_DEFINITIONS
]


async def get_z_ai_coding_plan_models() -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in Z_AI_CODING_PLAN_MODELS]
