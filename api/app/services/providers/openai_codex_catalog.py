import re
from typing import Any

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.providers.common import MERIDIAN_SUPPORTED_TOOL_NAMES
from services.providers.models_dev import get_models_dev_provider_models

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


def get_openai_codex_image_generation_base_model_id(model_id: str) -> str:
    base_model_id = get_openai_codex_base_model_id(model_id).removeprefix(OPENAI_CODEX_MODEL_PREFIX)
    if base_model_id.endswith("-pro"):
        return base_model_id[: -len("-pro")]
    return base_model_id


def _normalize_input_modalities(input_modalities: Any) -> list[str]:
    if not isinstance(input_modalities, list):
        return list(OPENAI_CODEX_DEFAULT_INPUT_MODALITIES)

    normalized = [str(modality).strip().lower() for modality in input_modalities if modality]
    return normalized or list(OPENAI_CODEX_DEFAULT_INPUT_MODALITIES)


def _get_models_dev_input_modalities(payload: dict[str, Any]) -> Any:
    modalities = payload.get("modalities")
    if isinstance(modalities, dict):
        return modalities.get("input")
    return None


def _get_context_length(payload: dict[str, Any]) -> int:
    context_length = payload.get("contextLength")
    if isinstance(context_length, int):
        return context_length

    limit = payload.get("limit")
    if isinstance(limit, dict) and isinstance(limit.get("context"), int):
        return int(limit["context"])
    return -1


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

    display_name = str(payload.get("name") or "").strip()
    if not display_name:
        display_name = str(model_id).strip().replace("gpt", "GPT", 1) or model_id
    input_modalities = _normalize_input_modalities(
        payload.get("inputModalities") or _get_models_dev_input_modalities(payload)
    )
    default_reasoning_effort = str(payload.get("defaultReasoningEffort") or "").strip()
    supported_reasoning_efforts = payload.get("supportedReasoningEfforts")
    context_length = _get_context_length(payload)

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
        context_length=context_length,
        pricing=Pricing(prompt="0", completion="0", internal_reasoning=internal_reasoning),
        provider=InferenceProviderEnum.OPENAI_CODEX,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=True,
        supportsMeridianTools=True,
        supportedMeridianToolNames=list(OPENAI_CODEX_SUPPORTED_TOOL_NAMES),
        toolsSupport=True,
    )


def is_models_dev_openai_codex_model(model_id: str) -> bool:
    if "codex" in model_id:
        return True

    match = re.match(r"^gpt-(\d+\.\d+)", model_id)
    if not match:
        return False
    try:
        return float(match.group(1)) >= 5.4 and not model_id.endswith("-nano")
    except ValueError:
        return False


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


def _select_openai_codex_image_generation_base_model(models: list[ModelInfo]) -> ModelInfo | None:
    if not models:
        return None
    for model in models:
        base_model_id = get_openai_codex_base_model_id(model.id).removeprefix(
            OPENAI_CODEX_MODEL_PREFIX
        )
        if not base_model_id.endswith("-pro"):
            return model
    return models[0]


def build_openai_codex_models_from_models_dev(payload: Any) -> list[ModelInfo]:
    models_payload = get_models_dev_provider_models(payload, "openai")
    if not models_payload:
        return []

    normalized_models: list[ModelInfo] = []
    seen_model_ids: set[str] = set()
    for model_id, raw_model in models_payload.items():
        resolved_model_id = str(model_id or "").strip()
        if not resolved_model_id or not is_models_dev_openai_codex_model(resolved_model_id):
            continue
        if not isinstance(raw_model, dict):
            continue
        normalized_model = normalize_openai_codex_model({"id": resolved_model_id, **raw_model})
        if normalized_model is None or normalized_model.id in seen_model_ids:
            continue
        seen_model_ids.add(normalized_model.id)
        normalized_models.append(normalized_model)

    normalized_models.sort(key=lambda model: model.id, reverse=True)
    if normalized_models:
        image_base_model = _select_openai_codex_image_generation_base_model(normalized_models)
        if image_base_model is not None:
            normalized_models.insert(0, build_openai_codex_image_generation_model(image_base_model))
        return normalized_models
    return []


async def get_models_dev_openai_codex_models(models_dev_catalog: Any) -> list[ModelInfo]:
    return build_openai_codex_models_from_models_dev(models_dev_catalog)
