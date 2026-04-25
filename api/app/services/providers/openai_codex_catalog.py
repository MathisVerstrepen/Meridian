from typing import Any

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.providers.common import MERIDIAN_SUPPORTED_TOOL_NAMES

OPENAI_CODEX_PROVIDER_KEY = "openai_codex.auth_json"
OPENAI_CODEX_MODEL_PREFIX = "openai-codex/"
OPENAI_CODEX_IMAGE_GENERATION_MODEL_SUFFIX = ":image-generation"
OPENAI_CODEX_LABEL = "OpenAI Codex"
OPENAI_CODEX_SUPPORTED_TOOL_NAMES = list(MERIDIAN_SUPPORTED_TOOL_NAMES)
OPENAI_CODEX_DEFAULT_INPUT_MODALITIES = ["text", "image"]


def is_openai_codex_image_generation_model(model_id: str) -> bool:
    return model_id.endswith(OPENAI_CODEX_IMAGE_GENERATION_MODEL_SUFFIX)


def get_openai_codex_base_model_id(model_id: str) -> str:
    if is_openai_codex_image_generation_model(model_id):
        return model_id[: -len(OPENAI_CODEX_IMAGE_GENERATION_MODEL_SUFFIX)]
    return model_id


def _normalize_input_modalities(input_modalities: Any) -> list[str]:
    if not isinstance(input_modalities, list):
        return list(OPENAI_CODEX_DEFAULT_INPUT_MODALITIES)

    normalized = [str(modality).strip().lower() for modality in input_modalities if modality]
    return normalized or list(OPENAI_CODEX_DEFAULT_INPUT_MODALITIES)


def _build_modality_description(input_modalities: list[str]) -> str:
    unique_modalities: list[str] = []
    for modality in input_modalities:
        if modality not in unique_modalities:
            unique_modalities.append(modality)

    if not unique_modalities:
        unique_modalities = list(OPENAI_CODEX_DEFAULT_INPUT_MODALITIES)

    return f"{' + '.join(unique_modalities)}->text"


def normalize_openai_codex_model(payload: Any) -> ModelInfo | None:
    if not isinstance(payload, dict):
        return None

    model_id = str(payload.get("model") or payload.get("id") or "").strip()
    if not model_id:
        return None

    display_name = str(model_id).strip().replace("gpt", "GPT", 1) or model_id
    input_modalities = _normalize_input_modalities(payload.get("inputModalities"))
    default_reasoning_effort = str(payload.get("defaultReasoningEffort") or "").strip()
    supported_reasoning_efforts = payload.get("supportedReasoningEfforts")
    context_length = payload.get("contextLength")

    internal_reasoning = None
    if default_reasoning_effort:
        internal_reasoning = default_reasoning_effort
    elif isinstance(supported_reasoning_efforts, list) and supported_reasoning_efforts:
        internal_reasoning = (
            str(
                supported_reasoning_efforts[0].get("reasoningEffort")
                if isinstance(supported_reasoning_efforts[0], dict)
                else supported_reasoning_efforts[0]
            ).strip()
            or None
        )

    return ModelInfo(
        id=f"{OPENAI_CODEX_MODEL_PREFIX}{model_id}",
        name=display_name,
        icon="openai",
        architecture=Architecture(
            input_modalities=input_modalities,
            modality=_build_modality_description(input_modalities),
            output_modalities=["text"],
            tokenizer="gpt",
        ),
        context_length=(int(context_length) if isinstance(context_length, int) else -1),
        pricing=Pricing(prompt="0", completion="0", internal_reasoning=internal_reasoning),
        provider=InferenceProviderEnum.OPENAI_CODEX,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=True,
        supportsMeridianTools=True,
        supportedMeridianToolNames=list(OPENAI_CODEX_SUPPORTED_TOOL_NAMES),
        toolsSupport=True,
    )


def build_openai_codex_image_generation_model(base_model: ModelInfo) -> ModelInfo:
    return base_model.model_copy(
        deep=True,
        update={
            "id": f"{base_model.id}{OPENAI_CODEX_IMAGE_GENERATION_MODEL_SUFFIX}",
            "name": "Codex Image Generation",
            "architecture": Architecture(
                input_modalities=list(OPENAI_CODEX_DEFAULT_INPUT_MODALITIES),
                modality="text + image->image",
                output_modalities=["image"],
                tokenizer=base_model.architecture.tokenizer,
            ),
            "pricing": Pricing(prompt="0", completion="0", image="0"),
            "supportsStructuredOutputs": False,
            "supportsMeridianTools": False,
            "supportedMeridianToolNames": [],
            "toolsSupport": False,
        },
    )
